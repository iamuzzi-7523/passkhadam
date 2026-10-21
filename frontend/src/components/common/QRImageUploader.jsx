import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, CheckCircle, AlertCircle, FileCheck, RefreshCw } from 'lucide-react';

export default function QRImageUploader({ onVerify, isVerifying, roleTitle = "Verifier" }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
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
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleSubmit = () => {
    if (selectedFile && onVerify) {
      onVerify(selectedFile);
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
              <div className="flex items-center gap-2 mt-2">
                <button
                  onClick={handleReset}
                  disabled={isVerifying}
                  className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 underline"
                >
                  <RefreshCw className="w-3 h-3" />
                  Choose Different Image
                </button>
              </div>
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isVerifying}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-semibold text-sm shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
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
