"""
Incremental AST Indexer for ContextPacket generation.

Note: This is an approximate v1 heuristic. It collapses imports by bare module name,
meaning package-qualified imports or identical basenames across different directories
may cause false positive reverse dependencies. Also, it only walks top-level AST body nodes,
so nested or conditionally defined classes/methods remain invisible.
"""
import ast
import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

SYMBOLS_INDEX_VERSION = 3
CONTEXT_PACKET_MAX_CHARS = 3500

def parse_file_symbols(file_path: Path) -> Dict[str, Any]:
    """
    Parses a Python, JavaScript, or TypeScript file to extract top-level imports, classes (with methods), and functions.
    Non-supported files are silently ignored (returns language 'unsupported').
    """
    suffix = file_path.suffix.lower()
    if suffix not in ('.py', '.js', '.jsx', '.ts', '.tsx'):
        return {'language': 'unsupported'}
        
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {'error': f'Read error: {str(e)}'}

    if suffix == '.py':
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            return {'error': f'SyntaxError: {str(e)}'}

        imports = []
        classes = []
        functions = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.ClassDef):
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args]
                        sig = f"{item.name}({', '.join(args)})"
                        methods.append(sig)
                classes.append({'name': node.name, 'methods': methods})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                sig = f"{node.name}({', '.join(args)})"
                functions.append(sig)

        return {
            'language': 'python',
            'imports': list(set(imports)),
            'classes': classes,
            'functions': functions
        }
    else:
        # Heuristic JS/TS parser
        import re
        imports = []
        
        # Standard imports: import ... from 'module'
        imports.extend(re.findall(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", content))
        
        # Require calls: require('module')
        imports.extend(re.findall(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content))
        
        # Dynamic imports: import('module')
        imports.extend(re.findall(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content))
        
        # Bare imports: import 'module'
        imports.extend(re.findall(r"import\s+['\"]([^'\"]+)['\"]", content))
        
        # Deduplicate
        imports = list(set(imports))

        functions = []
        func_decls = re.findall(r"function\s+([a-zA-Z0-9_$]+)\s*\(", content)
        for f in func_decls:
            functions.append(f"{f}()")
        
        arrow_funcs = re.findall(r"const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>", content)
        for f in arrow_funcs:
            functions.append(f"{f}()")

        classes = []
        class_decls = re.findall(r"class\s+([a-zA-Z0-9_$]+)", content)
        for c in class_decls:
            classes.append({'name': c, 'methods': []})

        return {
            'language': 'javascript' if suffix in ('.js', '.jsx') else 'typescript',
            'imports': imports,
            'classes': classes,
            'functions': list(set(functions))
        }

def get_file_hash(file_path: Path) -> str:
    """Fallback hash to detect changes if mtime is suspicious."""
    h = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def build_or_update_symbols_index(workspace_root: Path, force_walk: bool = False) -> Dict[str, Any]:
    """
    Scans the workspace for Python files.
    - Skips directory walk if index is < 300s old (unless forced).
    - Reuses cached data if mtime & size match.
    - Prunes missing files.
    - Rebuilds reverse dependency graph.
    """
    import time
    index_path = workspace_root / '.walkie' / 'symbols_index.json'
    
    # Load existing index
    index_data = {}
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # TTL optimization: skip walk if index is young
            if not force_walk and time.time() - index_path.stat().st_mtime < 300:
                if index_data.get('version') == SYMBOLS_INDEX_VERSION:
                    return index_data
        except Exception:
            index_data = {}
            
    if index_data.get('version') != SYMBOLS_INDEX_VERSION:
        index_data = {'version': SYMBOLS_INDEX_VERSION, 'files': {}}

    files_cache = index_data.get('files', {})
    
    current_files = set()
    
    # Walk workspace, skipping common ignore dirs
    ignore_dirs = {'.git', '.walkie', 'venv', 'node_modules', '__pycache__', 'dist', 'build'}
    
    for root, dirs, files in os.walk(workspace_root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in ('.py', '.js', '.jsx', '.ts', '.tsx'):
                continue
            
            full_path = Path(root) / file
            try:
                rel_path = full_path.relative_to(workspace_root).as_posix()
            except ValueError:
                continue
                
            current_files.add(rel_path)
            
            try:
                stat = full_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size
            except Exception:
                continue
                
            cached = files_cache.get(rel_path)
            # Re-parse if modified
            if not cached or cached.get('mtime') != mtime or cached.get('size') != size:
                # Optionally use hash fallback here if needed, but mtime/size is usually sufficient
                symbols = parse_file_symbols(full_path)
                symbols['mtime'] = mtime
                symbols['size'] = size
                files_cache[rel_path] = symbols

    # Prune ghost files (deleted or renamed)
    stale_paths = set(files_cache.keys()) - current_files
    for p in stale_paths:
        del files_cache[p]
        
    # Rebuild reverse import graph (raw: import string -> importing files)
    reverse_deps = {}
    for rel_path, data in files_cache.items():
        if data.get('language') not in ('python', 'javascript', 'typescript'):
            continue
            
        imports = data.get('imports', [])
        for imp in imports:
            if imp not in reverse_deps:
                reverse_deps[imp] = []
            if rel_path not in reverse_deps[imp]:
                reverse_deps[imp].append(rel_path)
    
    # Build resolved reverse deps: target_file_rel_path -> set of importing_file_rel_path
    # First, create a lookup of all files by potential import keys
    file_lookup = {}  # key -> set of rel_paths
    for rel_path in current_files:
        p = Path(rel_path)
        stem = p.stem
        # Key: full path without extension
        no_ext = rel_path[:-len(p.suffix)] if p.suffix else rel_path
        file_lookup.setdefault(no_ext, set()).add(rel_path)
        # Key: stem (filename without extension)
        file_lookup.setdefault(stem, set()).add(rel_path)
        # Key: @/ alias if under src/
        if no_ext.startswith('src/'):
            at_key = '@/'+no_ext[4:]
            file_lookup.setdefault(at_key, set()).add(rel_path)
        # Key: parent directory (for index files)
        # e.g., src/components/index.tsx -> src/components
        if stem == 'index':
            parent_key = str(p.parent).replace('\\', '/')
            if parent_key != '.':
                file_lookup.setdefault(parent_key, set()).add(rel_path)
    
    # Helper to resolve an import string to target file(s)
    def resolve_import(imp: str, importing_rel: str) -> Set[str]:
        targets = set()
        importing_dir = Path(importing_rel).parent
        
        # Relative imports
        if imp.startswith('.'):
            # Resolve relative to importing file's directory
            # Normalize path
            resolved = (importing_dir / imp).as_posix()
            # Normalize .. and .
            parts = []
            for part in resolved.split('/'):
                if part == '..':
                    if parts:
                        parts.pop()
                elif part and part != '.':
                    parts.append(part)
            resolved = '/'.join(parts)
            
            # Try exact match (with extensions)
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = resolved + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try as directory with index file
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = resolved + '/index' + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try without extension (in case it's already in file_lookup)
            if resolved in file_lookup:
                targets.update(file_lookup[resolved])
                
        # @/ alias
        elif imp.startswith('@/'):
            # Convert @/ to src/
            converted = 'src/' + imp[2:]
            # Try exact match with extensions
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = converted + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try as directory with index
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = converted + '/index' + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try file_lookup
            if converted in file_lookup:
                targets.update(file_lookup[converted])
                
        # Absolute from root or bare
        else:
            # Try as absolute path from root
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = imp + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try as directory with index
            for ext in ('.ts', '.tsx', '.js', '.jsx', '.py'):
                candidate = imp + '/index' + ext
                if candidate in current_files:
                    targets.add(candidate)
            # Try file_lookup (matches stem, @/ key, etc.)
            if imp in file_lookup:
                targets.update(file_lookup[imp])
                
        return targets
    
    # Build resolved reverse deps
    resolved_reverse_deps = {}
    for rel_path, data in files_cache.items():
        if data.get('language') not in ('python', 'javascript', 'typescript'):
            continue
            
        imports = data.get('imports', [])
        for imp in imports:
            targets = resolve_import(imp, rel_path)
            for target in targets:
                resolved_reverse_deps.setdefault(target, set()).add(rel_path)
    
    # Convert sets to lists for JSON serialization
    resolved_reverse_deps = {k: list(v) for k, v in resolved_reverse_deps.items()}
    
    index_data['files'] = files_cache
    index_data['reverse_deps'] = reverse_deps
    index_data['resolved_reverse_deps'] = resolved_reverse_deps
    
    # Atomic save
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = index_path.with_suffix('.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2)
    tmp_path.replace(index_path)
    
    return index_data

def compile_context_packet(target_file: Path, workspace_root: Path, index_data: Dict[str, Any]) -> str:
    """
    Builds a truncated, scope-aware context packet prioritizing:
    1. Target file's signatures
    2. 1-hop dependencies (files imported by target)
    3. Reverse dependencies (files importing target)
    """
    try:
        rel_target = target_file.relative_to(workspace_root).as_posix()
    except ValueError:
        return ""
        
    files = index_data.get('files', {})
    reverse_deps = index_data.get('reverse_deps', {})
    
    target_data = files.get(rel_target)
    if not target_data or target_data.get('language') not in ('python', 'javascript', 'typescript'):
        return ""
        
    packet_lines = []
    packet_lines.append("--- ContextPacket ---")
    packet_lines.append(f"Target Module: {rel_target}")
    
    # 1. Target Signatures
    packet_lines.append("\n[Target Signatures]")
    for c in target_data.get('classes', []):
        packet_lines.append(f"class {c['name']}:")
        for m in c.get('methods', []):
            packet_lines.append(f"  def {m}")
    for f in target_data.get('functions', []):
        packet_lines.append(f"def {f}")
        
    # 2. Dependencies
    target_module_name = target_file.stem
    imports = target_data.get('imports', [])
    if imports:
        packet_lines.append("\n[Imports]")
        packet_lines.append(", ".join(imports))
        
    # 3. Reverse Dependencies (files that import this module)
    # Use resolved reverse deps which maps target file path -> importing files
    resolved_reverse_deps = index_data.get('resolved_reverse_deps', {})
    rev_deps = resolved_reverse_deps.get(rel_target, [])
    if rev_deps:
        packet_lines.append("\n[Reverse Dependencies]")
        packet_lines.append(", ".join(rev_deps))
        
    packet_lines.append("--- End ContextPacket ---\n")
    
    full_packet = "\n".join(packet_lines)
    
    # Priority Truncation Ladder
    if len(full_packet) > CONTEXT_PACKET_MAX_CHARS:
        # Step 1: Remove reverse dependencies
        rev_start = full_packet.find("\n[Reverse Dependencies]")
        if rev_start != -1:
            full_packet = full_packet[:rev_start] + "\n--- End ContextPacket ---\n"
            
    if len(full_packet) > CONTEXT_PACKET_MAX_CHARS:
        # Step 2: Remove imports
        imp_start = full_packet.find("\n[Imports]")
        if imp_start != -1:
            full_packet = full_packet[:imp_start] + "\n--- End ContextPacket ---\n"
            
    if len(full_packet) > CONTEXT_PACKET_MAX_CHARS:
        # Step 3: Hard truncate
        full_packet = full_packet[:CONTEXT_PACKET_MAX_CHARS - 50] + "\n...[truncated]\n--- End ContextPacket ---\n"
        
    return full_packet
