/**
 * Barcode scanning via camera.
 *
 * Strategy: use the native BarcodeDetector API when available (Chrome, Safari
 * on mobile), otherwise fall back to the QuaggaJS library loaded from CDN.
 *
 * On successful detection of an EAN-13 / ISBN barcode the value is placed into
 * the ISBN input field and the lookup form is submitted automatically via HTMX.
 */

(function () {
  "use strict";

  const video = document.getElementById("barcode-video");
  const startBtn = document.getElementById("start-scan-btn");
  const stopBtn = document.getElementById("stop-scan-btn");
  const torchBtn = document.getElementById("torch-btn");
  const statusEl = document.getElementById("scan-status");
  const isbnInput = document.getElementById("isbn-input");
  const viewfinder = document.getElementById("viewfinder");

  if (!video || !isbnInput) return;

  function isbnCheckDigit(digits) {
    // Verify ISBN-13 check digit (mod 10, alternating weights 1 and 3).
    var sum = 0;
    for (var i = 0; i < 12; i++) {
      sum += parseInt(digits[i], 10) * (i % 2 === 0 ? 1 : 3);
    }
    var check = (10 - (sum % 10)) % 10;
    return check === parseInt(digits[12], 10);
  }

  function isISBN(val) {
    if (!val || !/^\d{10,13}$/.test(val)) return false;
    // ISBN-13 must start with 978 or 979 and pass checksum
    if (val.length === 13) {
      return (val.startsWith("978") || val.startsWith("979")) && isbnCheckDigit(val);
    }
    // ISBN-10 is any 10-digit string
    return val.length === 10;
  }

  let scanning = false;
  let stream = null;
  let animationId = null;
  let torchOn = false;
  let usingQuagga = false;
  let lastRead = null;
  let readCount = 0;
  var REQUIRED_READS = 3;

  function setStatus(msg, isWarning) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.classList.toggle("text-amber-600", !!isWarning);
    statusEl.classList.toggle("dark:text-amber-400", !!isWarning);
    statusEl.classList.toggle("text-gray-600", !isWarning);
    statusEl.classList.toggle("dark:text-gray-400", !isWarning);
  }

  function flashSuccess() {
    viewfinder.classList.add("scan-success");
    setTimeout(() => viewfinder.classList.remove("scan-success"), 600);
  }

  function onDetected(isbn) {
    if (!scanning) return;
    scanning = false;
    isbnInput.value = isbn;
    flashSuccess();

    // Trigger the HTMX form submission.
    const form = isbnInput.closest("form");
    if (form) htmx.trigger(form, "submit");

    stopScanning();
  }

  // --- Native BarcodeDetector path ---

  function confirmRead(val) {
    // Require REQUIRED_READS consistent reads before accepting.
    if (val === lastRead) {
      readCount++;
    } else {
      lastRead = val;
      readCount = 1;
    }
    return readCount >= REQUIRED_READS;
  }

  async function scanWithNative(detector) {
    if (!scanning) return;
    try {
      const barcodes = await detector.detect(video);
      for (const b of barcodes) {
        const val = b.rawValue;
        if (val && isISBN(val) && confirmRead(val)) {
          onDetected(val);
          return;
        }
      }
    } catch (_) {
      // Frame not ready yet — ignore.
    }
    animationId = requestAnimationFrame(() => scanWithNative(detector));
  }

  // --- QuaggaJS fallback path ---

  function startQuagga() {
    usingQuagga = true;
    Quagga.init(
      {
        inputStream: {
          name: "Live",
          type: "LiveStream",
          target: video.parentElement,
          constraints: {
            facingMode: "environment",
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
        },
        decoder: {
          readers: ["ean_reader"],
        },
        locate: true,
      },
      function (err) {
        if (err) {
          setStatus("Camera error: " + err.message);
          return;
        }
        Quagga.start();
        setStatus("Point camera at a barcode…");
      },
    );

    Quagga.onDetected(function (result) {
      const code = result.codeResult.code;
      if (code && isISBN(code) && confirmRead(code)) {
        Quagga.stop();
        onDetected(code);
      }
    });
  }

  // --- Camera helpers ---

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } },
      });
      video.srcObject = stream;
      await video.play();
      return true;
    } catch (e) {
      if (e.name === "NotAllowedError") {
        setStatus(
          "Camera access was denied. To enable it: open your browser settings, " +
            "find this site, and allow camera access. Then tap \"Start camera scan\" again.",
          true,
        );
      } else if (e.name === "NotFoundError") {
        setStatus("No camera found on this device. Use the manual input below.", true);
      } else {
        setStatus("Camera error: " + e.message + ". Use the manual input below.", true);
      }
      stopBtn.classList.add("hidden");
      startBtn.classList.remove("hidden");
      viewfinder.classList.add("hidden");
      return false;
    }
  }

  function supportsTorch() {
    if (!stream) return false;
    const track = stream.getVideoTracks()[0];
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    return caps.torch === true || (Array.isArray(caps.torch) && caps.torch.includes(true));
  }

  async function toggleTorch() {
    if (!stream) return;
    torchOn = !torchOn;
    const track = stream.getVideoTracks()[0];
    try {
      await track.applyConstraints({ advanced: [{ torch: torchOn }] });
      torchBtn.setAttribute("aria-pressed", torchOn);
    } catch (_) {
      // Torch not supported on this track.
    }
  }

  // --- Start / stop ---

  async function startScanning() {
    scanning = true;
    lastRead = null;
    readCount = 0;
    viewfinder.classList.remove("hidden");
    startBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    setStatus("Starting camera…");

    const hasNative =
      typeof BarcodeDetector !== "undefined" &&
      (await BarcodeDetector.getSupportedFormats()).includes("ean_13");

    if (hasNative) {
      const ok = await startCamera();
      if (!ok) return;
      const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8"] });
      setStatus("Point camera at a barcode…");
      scanWithNative(detector);
    } else if (typeof Quagga !== "undefined") {
      startQuagga();
    } else {
      // Dynamically load QuaggaJS.
      setStatus("Loading barcode library…");
      const script = document.createElement("script");
      script.src =
        "https://cdn.jsdelivr.net/npm/@ericblade/quagga2@1.8.4/dist/quagga.min.js";
      script.onload = () => startQuagga();
      script.onerror = () =>
        setStatus("Could not load barcode library. Use manual input.");
      document.head.appendChild(script);
    }

    if (stream && supportsTorch()) {
      torchBtn.classList.remove("hidden");
    }
  }

  function stopScanning() {
    scanning = false;
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
    if (usingQuagga && typeof Quagga !== "undefined") {
      try { Quagga.stop(); } catch (_) {}
      usingQuagga = false;
    }
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    video.srcObject = null;
    torchOn = false;
    viewfinder.classList.add("hidden");
    startBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
    torchBtn.classList.add("hidden");
    setStatus("");
  }

  startBtn.addEventListener("click", startScanning);
  stopBtn.addEventListener("click", stopScanning);
  torchBtn.addEventListener("click", toggleTorch);
})();
