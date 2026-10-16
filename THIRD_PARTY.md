# Third-party components

- **Seed-VC**, Plachtaa: GPL-3.0, source pinned to `51383efd921027683c89e5348211d93ff12ac2a8`. Downloaded separately from https://github.com/Plachtaa/seed-vc. The adapters use its training and OpenVoice modules. The complete downloaded source includes its license notices; it is not modified by the adapters.
- **OpenVoice V2**, MyShell: upstream code and model are MIT licensed. Model source: https://huggingface.co/myshell-ai/OpenVoiceV2, pinned to `f36e7edfe1684461a8343844af60babc2efbb727`. Weights are downloaded separately. The OpenVoice implementation used here is supplied with Seed-VC.
- **LJ Speech reference recording**: public domain/Unlicense per the source dataset card. See [reference provenance](assets/voices/NOTICE.md). The reference recording is not covered by the application code's GPL license.
- **VCClient**, w-okada: separately downloaded voice-conversion software with its own code/model terms, https://github.com/w-okada/voice-changer.

VoiceBridge application code is provided under GPL-3.0; see [LICENSE](LICENSE). No warranty is provided. User-provided recordings and private model checkpoints are not redistributed with the source.
