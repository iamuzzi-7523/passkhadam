import React, { useState } from 'react';
import { Volume2, VolumeX, Mic, Radio } from 'lucide-react';
import { narrator } from '../../utils/speech';
import { getTranslation } from '../../i18n/translations';

export default function VoiceNarrator({ textToRead, currentLang = 'en', title = null }) {
  const [isPlaying, setIsPlaying] = useState(false);

  const handleToggle = () => {
    if (isPlaying) {
      narrator.stop();
      setIsPlaying(false);
    } else {
      narrator.speak(
        textToRead,
        currentLang,
        () => setIsPlaying(true),
        () => setIsPlaying(false),
        () => setIsPlaying(false)
      );
    }
  };

  return (
    <div className="inline-flex items-center gap-2 p-1.5 px-3 rounded-full bg-gradient-to-r from-blue-900/40 to-indigo-900/40 border border-blue-500/30 text-xs shadow-sm">
      <button
        type="button"
        onClick={handleToggle}
        className={`p-1.5 rounded-full transition ${
          isPlaying
            ? 'bg-rose-600 text-white animate-pulse'
            : 'bg-blue-600 hover:bg-blue-500 text-white'
        }`}
        title={isPlaying ? getTranslation(currentLang, 'stopAudio') : getTranslation(currentLang, 'listenGuide')}
      >
        {isPlaying ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
      </button>

      <span className="font-medium text-slate-200 text-[11px] select-none">
        {isPlaying ? (
          <span className="text-blue-300 flex items-center gap-1">
            <Radio className="w-3 h-3 animate-ping text-blue-400" />
            Speaking ({currentLang.toUpperCase()})...
          </span>
        ) : (
          title || getTranslation(currentLang, 'listenGuide')
        )}
      </span>

      {isPlaying && (
        <span className="flex items-center gap-0.5 text-blue-400 pl-1">
          <span className="w-1 h-2 bg-blue-400 rounded-full animate-bounce"></span>
          <span className="w-1 h-3 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]"></span>
          <span className="w-1 h-4 bg-blue-300 rounded-full animate-bounce [animation-delay:300ms]"></span>
          <span className="w-1 h-2 bg-indigo-300 rounded-full animate-bounce [animation-delay:450ms]"></span>
        </span>
      )}
    </div>
  );
}
