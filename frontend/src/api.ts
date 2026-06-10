export type EmbedPayload = {
  image: File;
  watermark: File;
  passwordImg: number;
  passwordWm: number;
  outputFormat: 'png' | 'jpg';
};

export type ExtractPayload = {
  image: File;
  passwordImg: number;
  passwordWm: number;
  width: number;
  height: number;
};

async function requestBlob(path: string, formData: FormData): Promise<Blob> {
  const response = await fetch(path, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`;
    const body = await response.text().catch(() => fallback);
    const message = parseErrorMessage(body) || fallback;
    throw new Error(message || fallback);
  }

  return response.blob();
}

export async function embedWatermark(payload: EmbedPayload): Promise<Blob> {
  const formData = new FormData();
  formData.append('image', payload.image);
  formData.append('watermark', payload.watermark);
  formData.append('password_img', String(payload.passwordImg));
  formData.append('password_wm', String(payload.passwordWm));
  formData.append('output_format', payload.outputFormat);

  return requestBlob('/api/embed', formData);
}

export async function extractWatermark(payload: ExtractPayload): Promise<Blob> {
  const formData = new FormData();
  formData.append('image', payload.image);
  formData.append('password_img', String(payload.passwordImg));
  formData.append('password_wm', String(payload.passwordWm));
  formData.append('wm_width', String(payload.width));
  formData.append('wm_height', String(payload.height));

  return requestBlob('/api/extract', formData);
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch('/api/health');
    return response.ok;
  } catch {
    return false;
  }
}

function parseErrorMessage(body: string): string {
  try {
    const data = JSON.parse(body) as { detail?: unknown };
    if (typeof data.detail === 'string') return data.detail;
  } catch {
    return body;
  }

  return body;
}
