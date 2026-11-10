import { useEffect, useRef, useState, type PointerEvent } from "react";
import { apiRequest } from "../services/api/client";
import { message, type Step } from "../types";

export default function VisualCapture({
  onAdd,
}: {
  onAdd: (step: Step) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const image = useRef<HTMLImageElement | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [source, setSource] = useState("");
  const [mode, setMode] = useState<"point" | "image">("image");
  const [intent, setIntent] = useState<"click" | "assert" | "wait">("click");
  const [windowName, setWindowName] = useState("Navegador");
  const [selection, setSelection] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  async function captureScreen() {
    setFeedback("");
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setFeedback(
        "Captura direta indisponível neste navegador. Carregue uma captura de tela pelo arquivo.",
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });
      try {
        const video = document.createElement("video");
        video.srcObject = stream;
        await video.play();
        const frame = document.createElement("canvas");
        frame.width = video.videoWidth;
        frame.height = video.videoHeight;
        frame.getContext("2d")!.drawImage(video, 0, 0);
        const blob = await new Promise<Blob>((resolve, reject) =>
          frame.toBlob(
            (value) =>
              value
                ? resolve(value)
                : reject(new Error("Não foi possível capturar a tela.")),
            "image/png",
          ),
        );
        setSource(URL.createObjectURL(blob));
        setSelection(null);
      } finally {
        stream.getTracks().forEach((track) => track.stop());
      }
    } catch {
      setFeedback(
        "A captura não foi autorizada ou não está disponível. Você também pode carregar uma imagem.",
      );
    }
  }
  useEffect(() => {
    if (!source) return;
    const loaded = new Image();
    loaded.onload = () => {
      if (
        loaded.naturalWidth > 16000 ||
        loaded.naturalHeight > 16000 ||
        loaded.naturalWidth * loaded.naturalHeight > 25_000_000
      ) {
        setFeedback(
          "Imagem muito grande. Use uma captura de até 25 megapixels.",
        );
        return;
      }
      image.current = loaded;
      const target = canvas.current;
      if (target) {
        target.width = loaded.naturalWidth;
        target.height = loaded.naturalHeight;
        target.getContext("2d")?.drawImage(loaded, 0, 0);
      }
    };
    loaded.src = source;
    return () => {
      URL.revokeObjectURL(source);
      image.current = null;
    };
  }, [source]);
  function position(event: PointerEvent<HTMLCanvasElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(
          event.currentTarget.width - 1,
          Math.round(
            ((event.clientX - bounds.left) * event.currentTarget.width) /
              bounds.width,
          ),
        ),
      ),
      y: Math.max(
        0,
        Math.min(
          event.currentTarget.height - 1,
          Math.round(
            ((event.clientY - bounds.top) * event.currentTarget.height) /
              bounds.height,
          ),
        ),
      ),
    };
  }
  function finish(event: PointerEvent<HTMLCanvasElement>) {
    if (!start.current || !image.current) return;
    const end = position(event),
      origin = start.current;
    const region =
      mode === "point"
        ? { ...end, width: 1, height: 1 }
        : {
            x: Math.min(origin.x, end.x),
            y: Math.min(origin.y, end.y),
            width: Math.abs(end.x - origin.x),
            height: Math.abs(end.y - origin.y),
          };
    start.current = null;
    setSelection(region);
    const context = canvas.current!.getContext("2d")!;
    context.drawImage(image.current, 0, 0);
    context.strokeStyle = "#8c63ff";
    context.lineWidth = Math.max(2, image.current.width / 500);
    if (mode === "point") {
      context.beginPath();
      context.arc(end.x, end.y, 12, 0, Math.PI * 2);
      context.stroke();
    } else context.strokeRect(region.x, region.y, region.width, region.height);
  }
  async function add() {
    if (!selection || !image.current) return;
    setBusy(true);
    setFeedback("");
    const context = {
      x: selection.x,
      y: selection.y,
      width: image.current.width,
      height: image.current.height,
      window: windowName,
    };
    try {
      let reference: string | null = null;
      if (mode === "image") {
        if (
          selection.width < 8 ||
          selection.height < 8 ||
          selection.width > 1200 ||
          selection.height > 1200
        )
          throw new Error(
            "Selecione um botão entre 8 e 1200 pixels por dimensão.",
          );
        const crop = document.createElement("canvas");
        crop.width = selection.width;
        crop.height = selection.height;
        crop
          .getContext("2d")!
          .drawImage(
            image.current,
            selection.x,
            selection.y,
            selection.width,
            selection.height,
            0,
            0,
            selection.width,
            selection.height,
          );
        const blob = await new Promise<Blob>((resolve, reject) =>
          crop.toBlob(
            (value) =>
              value
                ? resolve(value)
                : reject(new Error("Não foi possível criar o recorte.")),
            "image/png",
          ),
        );
        reference = (
          await apiRequest<{ id: string }>("/reference-images", {
            method: "POST",
            body: blob,
            headers: { "Content-Type": "image/png" },
          })
        ).id;
      }
      onAdd({
        action:
          mode === "point"
            ? "click_point"
            : intent === "assert"
              ? "assert_image"
              : intent === "wait"
                ? "wait_image"
                : "click_image",
        locator: "",
        value: "",
        data_ref: "",
        timeout_seconds: 30,
        success_condition: "",
        screen_context: context,
        button_text: "",
        reference_image_id: reference,
        confidence: 0.9,
      });
      setFeedback(
        mode === "point"
          ? "Click point adicionado ao fluxo."
          : "Reconhecimento do botão adicionado. Apenas o recorte foi enviado ao servidor.",
      );
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="visual-capture">
      <div className="panel-title">
        <div>
          <h3>Captura visual</h3>
          <p>Use uma captura de tela para escolher o alvo da ação.</p>
        </div>
        <div className="actions">
          <span className="chip">CLICK POINT + IMAGEM</span>
          <button
            type="button"
            className="button small ghost"
            onClick={() => void captureScreen()}
          >
            Capturar tela
          </button>
        </div>
      </div>
      <div className="notice">
        A captura completa fica neste navegador. Para reconhecimento, salve
        apenas um recorte do botão sem dados pessoais ou credenciais. No
        navegador, capture apenas a área da página, sem a barra de endereços. No
        desktop, use a tela inteira.
      </div>
      <div className="form-grid">
        <label>
          Captura da plataforma
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file && file.size < 12_000_000) {
                setSource(URL.createObjectURL(file));
                setSelection(null);
                setFeedback("");
              } else setFeedback("Use uma imagem de até 12 MB.");
            }}
          />
        </label>
        <label>
          Janela esperada
          <input
            required
            value={windowName}
            onChange={(event) => setWindowName(event.target.value)}
            placeholder="Título da janela do programa"
          />
        </label>
        <label>
          Método
          <select
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as "point" | "image");
              setSelection(null);
            }}
          >
            <option value="image">Reconhecer botão pela imagem</option>
            <option value="point">Click point por coordenada</option>
          </select>
        </label>
        {mode === "image" && (
          <label>
            Ao reconhecer a imagem
            <select
              value={intent}
              onChange={(event) =>
                setIntent(event.target.value as "click" | "assert" | "wait")
              }
            >
              <option value="click">Clicar no botão</option>
              <option value="assert">Confirmar presença (sem clicar)</option>
              <option value="wait">Aguardar imagem aparecer</option>
            </select>
          </label>
        )}
      </div>
      {source ? (
        <>
          <p className="muted">
            {mode === "image"
              ? "Arraste um retângulo em volta do botão."
              : "Clique no ponto da tela que deseja usar."}
          </p>
          <div className="capture-canvas">
            <canvas
              ref={canvas}
              aria-label="Captura da plataforma para selecionar o botão"
              onPointerDown={(event) => {
                event.currentTarget.setPointerCapture(event.pointerId);
                start.current = position(event);
              }}
              onPointerUp={finish}
              onPointerCancel={() => {
                start.current = null;
              }}
            />
          </div>
          {selection && (
            <div className="actions capture-result">
              <span className="muted">
                X {selection.x} · Y {selection.y}
                {mode === "image"
                  ? ` · ${selection.width} × ${selection.height} px`
                  : ""}
              </span>
              <button
                type="button"
                className="button primary"
                disabled={busy || !windowName.trim()}
                onClick={() => void add()}
              >
                {busy ? "Preparando..." : "Adicionar ação ao fluxo"}
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="capture-placeholder">
          <span>⌖</span>
          <b>O seu fluxo começa com um alvo</b>
          <p>Carregue uma captura e selecione o botão ou ponto de clique.</p>
        </div>
      )}
      {feedback && (
        <p className="notice" role="status">
          {feedback}
        </p>
      )}
    </section>
  );
}
