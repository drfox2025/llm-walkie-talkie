const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const os = require('os');

const envPath = path.join(os.homedir(), '.walkie', '.env');

function copyDirRecursiveSync(src, dest) {
    if (!fs.existsSync(src)) return;
    const stats = fs.statSync(src);
    if (stats.isDirectory()) {
        if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });
        for (const file of fs.readdirSync(src)) {
            copyDirRecursiveSync(path.join(src, file), path.join(dest, file));
        }
    } else {
        fs.copyFileSync(src, dest);
    }
}

function readEnv() {
    if (!fs.existsSync(envPath)) return {};
    const content = fs.readFileSync(envPath, 'utf8');
    const env = {};
    for (const line of content.split(/\r?\n/)) {
        const match = line.match(/^\s*([\w.\-]+)\s*=\s*(.*)?$/);
        if (match) {
            let value = match[2] ? match[2].trim() : '';
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }
            env[match[1]] = value;
        }
    }
    return env;
}

function writeEnv(updatedEnv) {
    let content = '';
    if (fs.existsSync(envPath)) content = fs.readFileSync(envPath, 'utf8');
    const lines = content.split(/\r?\n/);
    const newLines = [];
    const writtenKeys = new Set();
    for (let line of lines) {
        const match = line.match(/^\s*([\w.\-]+)\s*=\s*(.*)?$/);
        if (match) {
            const key = match[1];
            if (Object.prototype.hasOwnProperty.call(updatedEnv, key)) {
                newLines.push(`${key}="${updatedEnv[key]}"`);
                writtenKeys.add(key);
            } else {
                newLines.push(line);
            }
        } else {
            newLines.push(line);
        }
    }
    for (const key of Object.keys(updatedEnv)) {
        if (!writtenKeys.has(key)) newLines.push(`${key}="${updatedEnv[key]}"`);
    }
    const dir = path.dirname(envPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(envPath, newLines.join('\n'), { encoding: 'utf8', mode: 0o600 });
}

// ── Env key mapping (flat .env key → data field) ─────────────────────────
const ENV_KEYS = {
    // API keys
    ZENMUX_API_KEY:           d => d.keys?.ZENMUX || '',
    GROQ_API_KEY:             d => d.keys?.GROQ || '',
    OPENROUTER_API_KEY:       d => d.keys?.OPENROUTER || '',
    OPENAI_API_KEY:           d => d.keys?.OPENAI || '',
    ANTHROPIC_API_KEY:        d => d.keys?.ANTHROPIC || '',
    GEMINI_API_KEY:           d => d.keys?.GEMINI || '',
    NVIDIA_API_KEY:           d => d.keys?.NVIDIA || '',
    NVIDIA_DEEPSEEK_API_KEY:  d => d.keys?.NVIDIA_DEEPSEEK || '',

    // Consult skill params
    LWT_DEFAULT_MODEL:        d => d.consultDefaultModel || '',
    LWT_CHAIN_MODEL:          d => d.consultChainModel || '',
    LWT_VERIFY_MODEL:         d => d.consultVerifyModel || '',
    LWT_RETRIES:              d => d.consultRetries != null ? String(d.consultRetries) : '',
    LWT_TIMEOUT:              d => d.consultTimeout != null ? String(d.consultTimeout) : '',
    LWT_DISCOVERY_TTL_HOURS:  d => d.consultCacheTTL != null ? String(d.consultCacheTTL) : '',
    LWT_CTX_BUFFER_LINES:     d => d.consultCtxBuf != null ? String(d.consultCtxBuf) : '',
    LWT_EXPERIENCE:           d => d.consultExperience != null ? (d.consultExperience ? '1' : '0') : '',
    LWT_DESIGN_CONTRACT:      d => d.consultDesignContract != null ? (d.consultDesignContract ? '1' : '0') : '',
    LWT_PROVIDER_PRIORITY:    d => d.consultProviderPriority || '',

    // Loop skill params
    LWT_LOOP_GEN_MODEL:       d => d.loopGenModel || '',
    LWT_LOOP_AUDIT_MODEL:     d => d.loopAuditModel || '',
    LWT_LOOP_REDTEAM_MODEL:   d => d.loopRedteamModel || '',
    LWT_LOOP_STOP_CMD:        d => d.loopStopCmd || '',
    LWT_MAX_ITERATIONS:       d => d.loopMaxIter != null ? String(d.loopMaxIter) : '',
    LWT_COST_CAP_USD:         d => d.loopCostCap != null ? String(d.loopCostCap) : '',
    LWT_LOOP_ITER_TIMEOUT:    d => d.loopIterTimeout != null ? String(d.loopIterTimeout) : '',
    LWT_LOOP_SESSION_ID:      d => d.loopSessionId || '',
    LWT_LOOP_CONTRACT_PATH:   d => d.loopContractPath || '',
    LWT_LOOP_SANDBOX:         d => d.loopSandbox != null ? (d.loopSandbox ? '1' : '0') : '',
    LWT_LOOP_OSCILLATION:     d => d.loopOscillation != null ? (d.loopOscillation ? '1' : '0') : '',
    LWT_LOOP_TOKEN_REPORT:    d => d.loopTokenReport != null ? (d.loopTokenReport ? '1' : '0') : '',

    // Routing
    LWT_DISCOVERY_INTERVAL:   d => d.routingDiscoveryInterval != null ? String(d.routingDiscoveryInterval) : '',
    LWT_HEALTH_TTL:           d => d.routingHealthTTL != null ? String(d.routingHealthTTL) : '',
    LWT_FAILOVER:             d => d.routingFailover != null ? (d.routingFailover ? '1' : '0') : '',
    LWT_SPOF_WARN:            d => d.routingSpofWarn != null ? (d.routingSpofWarn ? '1' : '0') : '',
    LWT_PROVIDER_ORDER:       d => Array.isArray(d.routingProviderOrder) ? d.routingProviderOrder.join(',') : '',

    // Behavior flags
    WALKIE_ALLOW_ABSOLUTE:    d => d.flagAllowAbsolute ? '1' : '0',
    WALKIE_DEBUG:             d => d.flagDebug ? '1' : '0',
    WALKIE_STREAM:            d => d.flagStream != null ? (d.flagStream ? '1' : '0') : '',
    WALKIE_MASK_KEYS:         d => d.flagMaskKeys != null ? (d.flagMaskKeys ? '1' : '0') : '',
    WALKIE_ATOMIC_WRITES:     d => d.flagAtomic != null ? (d.flagAtomic ? '1' : '0') : '',
    WALKIE_EVOLVE_BACKUP:     d => d.flagEvolveBackup != null ? (d.flagEvolveBackup ? '1' : '0') : '',
    SESSION_INJECT_TURNS:     d => d.flagSessionTurns != null ? String(d.flagSessionTurns) : '',
    SESSION_DIFF_CHAR_CAP:    d => d.flagDiffCap != null ? String(d.flagDiffCap) : '',
};

// ── Load settings for the webview ─────────────────────────────────────────
function buildLoadPayload(env) {
    return {
        keys: {
            ZENMUX:        env['ZENMUX_API_KEY'] || '',
            GROQ:          env['GROQ_API_KEY'] || '',
            OPENROUTER:    env['OPENROUTER_API_KEY'] || '',
            OPENAI:        env['OPENAI_API_KEY'] || '',
            ANTHROPIC:     env['ANTHROPIC_API_KEY'] || '',
            GEMINI:        env['GEMINI_API_KEY'] || '',
            NVIDIA:        env['NVIDIA_API_KEY'] || '',
            NVIDIA_DEEPSEEK: env['NVIDIA_DEEPSEEK_API_KEY'] || ''
        },
        consultDefaultModel:    env['LWT_DEFAULT_MODEL'] || '',
        consultChainModel:      env['LWT_CHAIN_MODEL'] || '',
        consultVerifyModel:     env['LWT_VERIFY_MODEL'] || '',
        consultRetries:         env['LWT_RETRIES'] ? parseInt(env['LWT_RETRIES'], 10) : undefined,
        consultTimeout:         env['LWT_TIMEOUT'] ? parseInt(env['LWT_TIMEOUT'], 10) : undefined,
        consultCacheTTL:        env['LWT_DISCOVERY_TTL_HOURS'] ? parseInt(env['LWT_DISCOVERY_TTL_HOURS'], 10) : undefined,
        consultCtxBuf:          env['LWT_CTX_BUFFER_LINES'] ? parseInt(env['LWT_CTX_BUFFER_LINES'], 10) : undefined,
        consultExperience:      env['LWT_EXPERIENCE'] !== '0',
        consultDesignContract:  env['LWT_DESIGN_CONTRACT'] !== '0',
        consultProviderPriority: env['LWT_PROVIDER_PRIORITY'] || '',

        loopGenModel:     env['LWT_LOOP_GEN_MODEL'] || '',
        loopAuditModel:   env['LWT_LOOP_AUDIT_MODEL'] || '',
        loopRedteamModel: env['LWT_LOOP_REDTEAM_MODEL'] || '',
        loopStopCmd:      env['LWT_LOOP_STOP_CMD'] || '',
        loopMaxIter:      env['LWT_MAX_ITERATIONS'] ? parseInt(env['LWT_MAX_ITERATIONS'], 10) : undefined,
        loopCostCap:      env['LWT_COST_CAP_USD'] ? parseFloat(env['LWT_COST_CAP_USD']) : undefined,
        loopIterTimeout:  env['LWT_LOOP_ITER_TIMEOUT'] ? parseInt(env['LWT_LOOP_ITER_TIMEOUT'], 10) : undefined,
        loopSessionId:    env['LWT_LOOP_SESSION_ID'] || '',
        loopContractPath: env['LWT_LOOP_CONTRACT_PATH'] || '',
        loopSandbox:      env['LWT_LOOP_SANDBOX'] !== '0',
        loopOscillation:  env['LWT_LOOP_OSCILLATION'] !== '0',
        loopTokenReport:  env['LWT_LOOP_TOKEN_REPORT'] !== '0',

        routingDiscoveryInterval: env['LWT_DISCOVERY_INTERVAL'] ? parseInt(env['LWT_DISCOVERY_INTERVAL'], 10) : undefined,
        routingHealthTTL:         env['LWT_HEALTH_TTL'] ? parseInt(env['LWT_HEALTH_TTL'], 10) : undefined,
        routingFailover:          env['LWT_FAILOVER'] !== '0',
        routingSpofWarn:          env['LWT_SPOF_WARN'] !== '0',
        routingProviderOrder:     env['LWT_PROVIDER_ORDER'] ? env['LWT_PROVIDER_ORDER'].split(',') : [],

        flagAllowAbsolute: env['WALKIE_ALLOW_ABSOLUTE'] === '1',
        flagDebug:         env['WALKIE_DEBUG'] === '1',
        flagStream:        env['WALKIE_STREAM'] !== '0',
        flagMaskKeys:      env['WALKIE_MASK_KEYS'] !== '0',
        flagAtomic:        env['WALKIE_ATOMIC_WRITES'] !== '0',
        flagEvolveBackup:  env['WALKIE_EVOLVE_BACKUP'] !== '0',
        flagSessionTurns:  env['SESSION_INJECT_TURNS'] ? parseInt(env['SESSION_INJECT_TURNS'], 10) : undefined,
        flagDiffCap:       env['SESSION_DIFF_CHAR_CAP'] ? parseInt(env['SESSION_DIFF_CHAR_CAP'], 10) : undefined,
    };
}

function activate(context) {
    console.log('LLM Walkie-Talkie extension activated.');

    const sourcePluginJson    = path.join(context.extensionPath, 'plugin.json');
    const sourceLogo          = path.join(context.extensionPath, 'logo.png');
    const sourceSkills        = path.join(context.extensionPath, 'skills');
    const sourcePreferencesUi = path.join(context.extensionPath, 'lwt-preferences-ui');
    const destDir = path.join(os.homedir(), '.gemini', 'config', 'plugins', 'llm-walkie-talkie');

    try {
        if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
        if (fs.existsSync(sourcePluginJson))    fs.copyFileSync(sourcePluginJson, path.join(destDir, 'plugin.json'));
        if (fs.existsSync(sourceLogo))          fs.copyFileSync(sourceLogo, path.join(destDir, 'logo.png'));
        if (fs.existsSync(sourceSkills))        copyDirRecursiveSync(sourceSkills, path.join(destDir, 'skills'));
        if (fs.existsSync(sourcePreferencesUi)) copyDirRecursiveSync(sourcePreferencesUi, path.join(destDir, 'lwt-preferences-ui'));
        console.log('LLM Walkie-Talkie global plugin files successfully installed/synchronized.');
    } catch (err) {
        console.error('Failed to copy LLM Walkie-Talkie plugin files:', err);
    }

    // Status bar button
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'llm-walkie-talkie.openPreferences';
    statusBarItem.text = '$(radio-tower) LWT';
    statusBarItem.tooltip = 'Open LLM Walkie-Talkie Control Panel';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Register webview command
    const disposable = vscode.commands.registerCommand('llm-walkie-talkie.openPreferences', () => {
        const uiFolder  = path.join(context.extensionPath, 'lwt-preferences-ui');
        const htmlPath  = path.join(uiFolder, 'index.html');

        if (!fs.existsSync(htmlPath)) {
            vscode.window.showErrorMessage('LWT Control Panel UI files not found.');
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'lwtControlPanel',
            'LWT — Bảng Điều Khiển',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.file(uiFolder)],
                retainContextWhenHidden: true
            }
        );

        let htmlContent = fs.readFileSync(htmlPath, 'utf8');
        const styleUri  = panel.webview.asWebviewUri(vscode.Uri.file(path.join(uiFolder, 'style.css')));
        const scriptUri = panel.webview.asWebviewUri(vscode.Uri.file(path.join(uiFolder, 'app.js')));
        htmlContent = htmlContent.replace('href="style.css"', `href="${styleUri}"`);
        htmlContent = htmlContent.replace('src="app.js"', `src="${scriptUri}"`);
        panel.webview.html = htmlContent;

        // Message bridge
        panel.webview.onDidReceiveMessage(message => {
            switch (message.command) {

                case 'requestSettings': {
                    const env = readEnv();
                    panel.webview.postMessage({
                        command: 'loadSettings',
                        data: buildLoadPayload(env)
                    });
                    break;
                }

                case 'saveSettings': {
                    try {
                        const d = message.data;
                        const currentEnv = readEnv();
                        // Apply all known mappings
                        for (const [envKey, getter] of Object.entries(ENV_KEYS)) {
                            const val = getter(d);
                            if (val !== '') currentEnv[envKey] = val;
                        }
                        writeEnv(currentEnv);
                        vscode.window.showInformationMessage(
                            '✓ LWT Control Panel — cấu hình đã lưu vào ~/.walkie/.env'
                        );
                    } catch (err) {
                        vscode.window.showErrorMessage(`LWT: Failed to save settings: ${err.message}`);
                    }
                    break;
                }

                case 'requestWorkspaceGraph': {
                    let graphData = '';
                    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
                        const workspaceRoot = vscode.workspace.workspaceFolders[0].uri.fsPath;
                        const statePath = path.join(workspaceRoot, '.walkie', 'state.md');
                        if (fs.existsSync(statePath)) {
                            graphData = fs.readFileSync(statePath, 'utf8');
                        }
                    }
                    panel.webview.postMessage({
                        command: 'loadWorkspaceGraph',
                        data: graphData
                    });
                    break;
                }
            }
        }, undefined, context.subscriptions);
    });

    context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = { activate, deactivate };
