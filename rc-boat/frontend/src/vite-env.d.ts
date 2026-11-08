/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL: string;
  readonly VITE_CAMERA_URL: string;
  readonly VITE_CAMERA_STATUS_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
