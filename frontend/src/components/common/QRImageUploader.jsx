import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, CheckCircle, AlertCircle, FileCheck, RefreshCw, Zap, Sparkles } from 'lucide-react';
import { apiFetch } from '../../utils/api';

export default function QRImageUploader({ onVerify, isVerifying, roleTitle = "Verifier", onSimulatePreset }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulateError, setSimulateError] = useState("");
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (file) => {
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setSimulateError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleSubmit = () => {
    if (selectedFile && onVerify) {
      onVerify(selectedFile);
    }
  };

  const handleSimulateScan = async () => {
    setIsSimulating(true);
    setSimulateError("");
    try {
      if (onSimulatePreset) {
        await onSimulatePreset();
        return;
      }

      // Role-aware demo endpoint
      const endpoint = roleTitle.toLowerCase().includes('government')
        ? '/api/v1/government/demo-worker-qr'
        : '/api/v1/employer/demo-worker-qr';

      let res = await apiFetch(endpoint);
      if (!res.ok) {
        // Fallback to general worker demo endpoint
        res = await apiFetch('/api/v1/worker/presentation/demo-qr');
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Unable to retrieve demo worker presentation");
      }

      const data = await res.json();
      if (!data.qr_base64_data_uri) {
        throw new Error("Invalid response format: missing QR image URI");
      }

      // Convert base64 Data URI to a native File object
      const blobRes = await fetch(data.qr_base64_data_uri);
      const blob = await blobRes.blob();
      const fileName = data.filename || `worker_presentation_${Date.now()}.png`;
      const simulatedFile = new File([blob], fileName, { type: "image/png" });

      // Update local preview
      setSelectedFile(simulatedFile);
      setPreviewUrl(data.qr_base64_data_uri);

      // 1-Click immediate verification trigger
      if (onVerify) {
        onVerify(simulatedFile);
      }
    } catch (err) {
      setSimulateError(err.message || "Failed to simulate scan");
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-blue-400" />
            Upload Worker QR Presentation
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Web-based verification. Drag & drop or choose the worker's presentation image.
          </p>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
          ✓ No Camera Needed
        </span>
      </div>

      {!previewUrl ? (
        <div className="space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current && inputRef.current.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center ${
              dragActive
                ? "border-blue-500 bg-blue-500/10 scale-[1.01]"
                : "border-slate-700/80 hover:border-slate-600 bg-slate-950/40"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              onChange={handleChange}
              className="hidden"
            />
            <div className="w-14 h-14 rounded-full bg-blue-600/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mb-3">
              <UploadCloud className="w-7 h-7" />
            </div>
            <p className="text-sm font-semibold text-slate-200">
              Drag & Drop Worker QR Image Here
            </p>
            <p className="text-xs text-slate-400 mt-1">
              or <span className="text-blue-400 underline font-medium">browse files</span> from your computer (PNG, JPG, WebP)
            </p>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-800" />
            </div>
            <div className="relative flex justify-center text-[11px] uppercase">
              <span className="bg-slate-900 px-3 text-slate-500 font-semibold tracking-wider">
                Or 1-Click Simulation
              </span>
            </div>
          </div>

          {/* 1-Click Simulation Card */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-blue-950/40 via-indigo-950/30 to-purple-950/40 border border-blue-500/30 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-bold text-white">Zero-Camera Demonstration Mode</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 text-[10px] font-semibold border border-blue-500/30">
                Preset Worker
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Instantly simulate an incoming physical QR scan from a verified migrant worker without browsing files or using camera hardware.
            </p>
            <button
              type="button"
              onClick={handleSimulateScan}
              disabled={isVerifying || isSimulating}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-semibold text-xs shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {isSimulating ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                  <span>Generating Ephemeral Demo Worker QR Presentation...</span>
                </>
              ) : (
                <>
                  <Zap className="w-3.5 h-3.5 text-amber-300" />
                  <span>⚡ 1-Click Simulate Scan from Worker Preset</span>
                </>
              )}
            </button>
            {simulateError && (
              <p className="text-xs text-rose-400 font-medium">{simulateError}</p>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="w-20 h-20 bg-white rounded-lg p-1.5 flex items-center justify-center shadow-md shrink-0">
              <img
                src={previewUrl}
                alt="Uploaded Worker QR"
                className="w-full h-full object-contain"
              />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">
                {selectedFile?.name || "worker_identity_presentation.png"}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Size: {(selectedFile?.size / 1024).toFixed(1)} KB • Ready for cryptographic audit
              </p>
              <div className="flex items-center gap-3 mt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={isVerifying || isSimulating}
                  className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 underline cursor-pointer"
                >
                  <RefreshCw className="w-3 h-3" />
                  Choose Different Image
                </button>
                <button
                  type="button"
                  onClick={handleSimulateScan}
                  disabled={isVerifying || isSimulating}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium underline cursor-pointer"
                >
                  <Zap className="w-3 h-3 text-amber-300" />
                  Simulate Fresh Worker QR
                </button>
              </div>
            </div>
          </div>

          {simulateError && (
            <p className="text-xs text-rose-400 font-medium">{simulateError}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={isVerifying || isSimulating}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-semibold text-sm shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
          >
            {isVerifying ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-white" />
                <span>Running Cryptographic Verification Engine...</span>
              </>
            ) : (
              <>
                <FileCheck className="w-4 h-4 text-white" />
                <span>Verify Worker Identity Now</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
