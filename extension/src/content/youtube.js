(() => {
  const PANEL_ID = "youtube-tutor-test-panel";
  const API_URL = "http://127.0.0.1:12701/api/test/video-data";

  function getVideoId() {
    const url = new URL(window.location.href);

    if (url.hostname === "youtu.be") {
      return url.pathname.slice(1).split("/")[0] || null;
    }

    if (url.pathname === "/watch") {
      return url.searchParams.get("v");
    }

    const pathParts = url.pathname.split("/").filter(Boolean);
    if (["shorts", "live", "embed"].includes(pathParts[0])) {
      return pathParts[1] || null;
    }

    return null;
  }

  function getVideo() {
    return document.querySelector("video.html5-main-video");
  }

  function getVideoTitle() {
    return document.querySelector("h1 yt-formatted-string")?.textContent?.trim()
      || document.title.replace(" - YouTube", "");
  }

  function getVideoData() {
    const video = getVideo();
    const videoId = getVideoId();

    if (!video || !videoId) {
      return null;
    }

    return {
      video_id: videoId,
      title: getVideoTitle(),
      url: window.location.href,
      video_duration: Number.isFinite(video.duration) ? video.duration : null,
      current_timestep: video.currentTime,
      is_playing: !video.paused && !video.ended && video.readyState > HTMLMediaElement.HAVE_CURRENT_DATA,
    };
  }

  function addMessage(messages, text, type) {
    const message = document.createElement("p");
    message.className = `message ${type}`;
    message.textContent = text;
    messages.append(message);
    messages.scrollTop = messages.scrollHeight;
  }

  async function submitCapture(input, messages, status) {
    const question = input.value.trim();
    if (!question) {
      return;
    }

    const videoData = getVideoData();
    if (!videoData) {
      status.textContent = "Open a playable YouTube video first.";
      return;
    }

    input.value = "";
    input.disabled = true;
    addMessage(messages, question, "user");
    status.textContent = "Saving video data and fetching transcript…";

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...videoData, message: question }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "The backend rejected the request.");
      }

      addMessage(messages, `Saved to ${result.file_name}. ${result.transcript_status}`, "assistant");
      status.textContent = `Captured at ${videoData.current_timestep.toFixed(1)} seconds.`;
    } catch (error) {
      console.error("YouTube Tutor test capture failed:", error);
      addMessage(messages, "Could not reach the local backend. Start FastAPI on port 12701.", "error");
      status.textContent = "Capture failed.";
    } finally {
      input.disabled = false;
      input.focus();
    }
  }

  function createPanel() {
    if (document.getElementById(PANEL_ID) || !getVideoId() || !getVideo()) {
      return;
    }

    const host = document.createElement("section");
    host.id = PANEL_ID;
    host.setAttribute("aria-label", "YouTube Tutor test chat");
    const shadow = host.attachShadow({ mode: "open" });

    shadow.innerHTML = `
      <style>
        :host { all: initial; }
        .panel { position: fixed; z-index: 2147483647; top: 86px; right: 18px; width: min(340px, calc(100vw - 36px)); box-sizing: border-box; color: #f5f5f5; background: #212121; border: 1px solid #3d3d3d; border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,.35); font: 14px/1.4 Arial, sans-serif; overflow: hidden; }
        header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid #3d3d3d; font-weight: 700; }
        button { border: 0; color: #aaa; background: transparent; cursor: pointer; font-size: 18px; }
        .messages { min-height: 94px; max-height: 230px; overflow-y: auto; padding: 10px 12px; }
        .message { margin: 0 0 8px; padding: 8px 10px; border-radius: 8px; white-space: pre-wrap; word-break: break-word; }
        .user { margin-left: 28px; background: #3f51b5; }
        .assistant { margin-right: 18px; background: #303030; }
        .error { background: #6e2525; }
        form { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid #3d3d3d; }
        input { min-width: 0; flex: 1; padding: 9px 10px; color: #f5f5f5; background: #121212; border: 1px solid #555; border-radius: 7px; outline: none; }
        input:focus { border-color: #8ab4f8; }
        .status { display: block; padding: 0 12px 10px; color: #aaa; font-size: 12px; }
      </style>
      <div class="panel">
        <header><span>YouTube Tutor — test chat</span><button type="button" aria-label="Close chat">×</button></header>
        <div class="messages" aria-live="polite"></div>
        <form><input type="text" placeholder="Ask a test question and press Enter" aria-label="Test question" autocomplete="off" /></form>
        <small class="status">Enter captures this video's current state.</small>
      </div>
    `;

    const closeButton = shadow.querySelector("button");
    const form = shadow.querySelector("form");
    const input = shadow.querySelector("input");
    const messages = shadow.querySelector(".messages");
    const status = shadow.querySelector(".status");

    for (const eventName of ["keydown", "keypress", "keyup"]) {
      shadow.addEventListener(eventName, (event) => event.stopPropagation());
    }

    addMessage(messages, "Enter a message to capture the current video timestamp and transcript.", "assistant");
    closeButton.addEventListener("click", () => host.remove());
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitCapture(input, messages, status);
    });

    document.documentElement.append(host);
  }

  function removePanelWhenLeavingVideo() {
    if (!getVideoId()) {
      document.getElementById(PANEL_ID)?.remove();
    }
  }

  const observer = new MutationObserver(() => {
    createPanel();
    removePanelWhenLeavingVideo();
  });

  observer.observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("yt-navigate-finish", createPanel);
  createPanel();
})();
