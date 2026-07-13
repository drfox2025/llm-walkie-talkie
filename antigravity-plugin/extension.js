const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const os = require('os');

function activate(context) {
    console.log('LLM Walkie-Talkie extension activated.');

    const sourcePluginJson = path.join(context.extensionPath, 'plugin.json');
    const sourceLogo = path.join(context.extensionPath, 'logo.png');
    const sourceSkill = path.join(context.extensionPath, 'skills', 'ai_consult', 'SKILL.md');

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

        // Copy skills/ai_consult/SKILL.md
        const destSkillsDir = path.join(destDir, 'skills', 'ai_consult');
        if (!fs.existsSync(destSkillsDir)) {
            fs.mkdirSync(destSkillsDir, { recursive: true });
        }
        
        if (fs.existsSync(sourceSkill)) {
            fs.copyFileSync(sourceSkill, path.join(destSkillsDir, 'SKILL.md'));
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
