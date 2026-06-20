{
  "thesis_id": "P4",
  "role": "source_pack",
  "findings": "Collected primary source evidence from official product launches, technical specifications, and independent reviews (2023–2026) confirming the trend toward always-on, on-device AI with privacy emphasis. Major device makers (Apple, Google, Samsung, Meta) have shipped hardware with dedicated low-power NPUs and local models (billion-parameter scale), while developer APIs for on-device AI have matured. However, battery/thermal complaints persist and no device yet achieves 'all-day context capture' without significant power draw, limiting the strength of the 'always-on' claim. The constraint thesis (low-power NPUs, sensor fusion, privacy orchestration) is well-supported by hardware specs and architecture disclosures, though privacy-preserving orchestration across heterogeneous sensors is only partially demonstrated in consumer products.",
  "proposed_nodes": [
    {
      "id": "n-source-apple-intelligence-2024-06",
      "kind": "source",
      "label": "Apple WWDC 2024 – Apple Intelligence with on-device processing",
      "fields": {
        "source_url": "https://www.apple.com/newsroom/2024/06/introducing-apple-intelligence-for-iphone-ipad-and-mac/",
        "source_date": "2024-06-10",
        "excerpt": "Apple Intelligence uses on-device processing to protect user privacy ... many models run entirely on device ... Private Cloud Compute extends privacy to the cloud but core features stay local.",
        "trust_rationale": "Official Apple press release; primary source.",
        "verification_status": "source_verified"
      },
      "confidence": 1.0
    },
    {
      "id": "n-source-google-gemini-nano-2023-12",
      "kind": "source",
      "label": "Google introduces Gemini Nano, on-device model for Pixel 8 Pro",
      "fields": {
        "source_url": "https://blog.google/products/pixel/gemini-nano-pixel-8-pro/",
        "source_date": "2023-12-06",
        "excerpt": "Gemini Nano is a 1.8-billion-parameter model that runs directly on Pixel 8 Pro, enabling features like
