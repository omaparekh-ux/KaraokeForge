# One-time Hugging Face setup

KaraokeForge uses a Hugging Face ZeroGPU Space for the free prototype backend.

## Create the Space

1. Sign in to Hugging Face.
2. Create a new Space named `KaraokeForge-Worker`.
3. Select **Gradio** as the SDK.
4. In the Space hardware settings, select **ZeroGPU**.
5. Keep the Space public so the web app can connect without a token.

ZeroGPU currently allows eligible free personal accounts to host up to two ZeroGPU Spaces and includes 5 GPU-minutes per day. ZeroGPU is currently Gradio-only. The quota is shared at the account tier rather than being a separate five minutes per Space. See Hugging Face's current ZeroGPU documentation for the latest limits. citeturn576858search0

## Connect GitHub Actions

In GitHub, open:

`Settings → Secrets and variables → Actions`

Create these repository secrets:

```text
HF_TOKEN=<your Hugging Face write token>
HF_SPACE_ID=<your-hugging-face-username>/KaraokeForge-Worker
```

The `Deploy KaraokeForge ZeroGPU Worker` workflow will then create/update the Space automatically whenever `hf_space/**` changes or whenever the workflow is manually dispatched.

## Connect the website

Open the deployed KaraokeForge website and enter the Space ID in **Processing engine**:

```text
<your-hugging-face-username>/KaraokeForge-Worker
```

Press **Save worker**. The value is stored in the browser, so it does not need to be entered for every song.

The web app uses the official Gradio JavaScript client to upload the user's file and submit the `forge` job. Gradio's current client supports browser file handling and queued status events. citeturn357765search1turn344325search0
