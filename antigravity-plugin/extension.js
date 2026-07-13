const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const os = require('os');

function copyDirRecursiveSync(src, dest) {
    if (!fs.existsSync(src)) {
        return;
    }
    const stats = fs.statSync(src);
    if (stats.isDirectory()) {
        if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
        }
        const files = fs.readdirSync(src);
        for (const file of files) {
            copyDirRecursiveSync(path.join(src, file), path.join(dest, file));
        }
    } else {
        fs.copyFileSync(src, dest);
    }
}

function activate(context) {
    console.log('LLM Walkie-Talkie extension activated.');

    const sourcePluginJson = path.join(context.extensionPath, 'plugin.json');
    const sourceLogo = path.join(context.extensionPath, 'logo.png');
    const sourceSkills = path.join(context.extensionPath, 'skills');

    // Target global plugins path: ~/.gemini/config/plugins/llm-walkie-talkie
    const destDir = path.join(os.homedir(), '.gemini', 'config', 'plugins', 'llm-walkie-talkie');

    try {
        // Create destination directory if it doesn't exist
        if (!fs.existsSync(destDir)) {
            fs.mkdirSync(destDir, { recursive: true });
        }

        // Copy plugin.json
        if (fs.existsSync(sourcePluginJson)) {
            fs.copyFileSync(sourcePluginJson, path.join(destDir, 'plugin.json'));
        }

        // Copy logo.png
        if (fs.existsSync(sourceLogo)) {
            fs.copyFileSync(sourceLogo, path.join(destDir, 'logo.png'));
        }

        // Copy all skills recursively
        if (fs.existsSync(sourceSkills)) {
            copyDirRecursiveSync(sourceSkills, path.join(destDir, 'skills'));
        }

        console.log('LLM Walkie-Talkie global plugin files successfully installed/synchronized.');
    } catch (err) {
        console.error('Failed to copy LLM Walkie-Talkie plugin files:', err);
    }
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
