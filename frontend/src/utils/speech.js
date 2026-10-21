// Browser Web Speech API Audio Narrator for PASSKHADAM Migrant Worker Support
// Speaks localized instructions in Hindi, Kannada, Bengali, Marathi, Telugu, and English

export class AudioNarrator {
  constructor() {
    this.synth = typeof window !== 'undefined' && 'speechSynthesis' in window ? window.speechSynthesis : null;
    this.currentUtterance = null;
    this.isPlaying = false;
    this.voices = [];

    if (this.synth) {
      this.loadVoices();
      if (this.synth.onvoiceschanged !== undefined) {
        this.synth.onvoiceschanged = () => this.loadVoices();
      }
    }
  }

  loadVoices() {
    if (!this.synth) return;
    this.voices = this.synth.getVoices();
  }

  isSupported() {
    return !!this.synth;
  }

  getVoiceForLang(langCode = 'en') {
    if (!this.voices || this.voices.length === 0) {
      this.loadVoices();
    }

    const langPrefixMap = {
      en: ['en-IN', 'en-US', 'en-GB', 'en'],
      hi: ['hi-IN', 'hi'],
      kn: ['kn-IN', 'kn'],
      bn: ['bn-IN', 'bn-BD', 'bn'],
      mr: ['mr-IN', 'mr'],
      te: ['te-IN', 'te']
    };

    const prefixes = langPrefixMap[langCode] || ['en'];

    for (const prefix of prefixes) {
      const match = this.voices.find(v => v.lang && v.lang.toLowerCase().startsWith(prefix.toLowerCase()));
      if (match) return match;
    }

    return this.voices.find(v => v.lang && v.lang.startsWith('en')) || this.voices[0] || null;
  }

  speak(text, lang = 'en', onStart = () => {}, onEnd = () => {}, onError = () => {}) {
    if (!this.synth) {
      console.warn('SpeechSynthesis is not supported in this browser.');
      onError('Not supported');
      return;
    }

    // Cancel any ongoing speech
    this.stop();

    if (!text || text.trim() === '') return;

    try {
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = this.getVoiceForLang(lang);
      if (voice) {
        utterance.voice = voice;
      }
      utterance.lang = lang === 'en' ? 'en-US' : `${lang}-IN`;
      utterance.rate = 0.95; // Slightly slower, clear cadence for migrant workers
      utterance.pitch = 1.0;

      utterance.onstart = () => {
        this.isPlaying = true;
        onStart();
      };

      utterance.onend = () => {
        this.isPlaying = false;
        this.currentUtterance = null;
        onEnd();
      };

      utterance.onerror = (e) => {
        this.isPlaying = false;
        this.currentUtterance = null;
        console.warn('Speech synthesis event error:', e);
        onError(e);
      };

      this.currentUtterance = utterance;
      this.synth.speak(utterance);
    } catch (err) {
      console.error('AudioNarrator speak error:', err);
      onError(err);
    }
  }

  stop() {
    if (this.synth) {
      this.synth.cancel();
      this.isPlaying = false;
      this.currentUtterance = null;
    }
  }
}

export const narrator = new AudioNarrator();
