# Publish AutoPatch to GitHub — Complete Windows Guide

The **GitHub tab inside the AutoPatch website** publishes the **current editor file** only. To upload **all source code and project files** (frontend, backend, tests, examples, documentation), use Git and the included `PUSH_TO_GITHUB.bat`.

## First-time upload (recommended)

1. Sign in to [GitHub](https://github.com).
2. Install [Git for Windows](https://git-scm.com/downloads/win) if you don't have it. Restart CMD after installing.
3. Open [Create a new repository](https://github.com/new). Set **Repository name** to `AutoPatch`, choose **Private** (recommended until you review the code), and **do not** initialize it with a README, .gitignore or license.
4. Click **Create repository**. Copy its HTTPS URL, e.g. `https://github.com/YOUR_USERNAME/AutoPatch.git`.
5. Open your extracted `AutoPatch_VSCODE_DEPLOY_READY` folder. Double-click `PUSH_TO_GITHUB.bat` or run it from CMD.
6. Paste the repository HTTPS URL. Enter your Git author name/email if asked. Review the files that Git lists, then press **Y** to commit and push.
7. When Git Credential Manager opens the GitHub sign-in flow, sign in with your GitHub account. **Never enter a GitHub password or token into chat.**
8. Refresh the repository page in your browser. You should see `frontend/`, `backend/`, `examples/`, `README.md` and the test workflow.

If you prefer to type the Git commands manually in CMD:

```cmd
git init -b main
git add .
git status --short
git commit -m "Initial AutoPatch project release"
git remote add origin https://github.com/YOUR_USERNAME/AutoPatch.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username. If Git reports an unknown author, set `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`, then retry. GitHub may require you to sign in via the browser.

## Future updates

From the same local project folder, use:

```cmd
git add .
git commit -m "Update AutoPatch"
git push
```

If your repository is **not empty**, the first push may be rejected because the histories differ. Do not force-push: use an empty new repository or reconcile the remote changes first.

## Security checklist

- Never commit `.env`, `.env.local`, API keys, GitHub tokens, private keys, resumes or personal data.
- `.gitignore` excludes common local secrets and build artifacts, but **it cannot catch secrets hardcoded inside other files**. Review `git status` and your source before uploading.
- Avoid adding `.venv/` or Python caches; they are machine-specific and unnecessary.
- Choose **Private** until you are comfortable sharing your code. You can change visibility in GitHub repository settings later.
- GitHub Actions runs Python tests on push; it does not execute untrusted source from the editor.

## Website's GitHub Studio tab

Open `http://127.0.0.1:8015`, paste code into Workspace, then choose GitHub. The form can create a personal repository or update one file in an existing repository using a Personal Access Token with appropriate permissions. Tokens are sent to the loopback backend for the GitHub HTTPS API request, not saved to disk, and cleared from the input after each attempt. **This is not the complete-project upload method.**
