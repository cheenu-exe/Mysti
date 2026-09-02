from __future__ import annotations
import asyncio

class VoiceInterface:
    def __init__(self, llm=None, transcriber=None, tts=None): self.llm,self.transcriber,self.tts=llm,transcriber,tts
    async def transcribe(self,audio:bytes)->str:
        if self.transcriber: return await self.transcriber(audio)
        try:
            import whisper
        except ImportError: raise RuntimeError("install openai-whisper or provide a transcriber")
        model=await asyncio.to_thread(whisper.load_model,"base"); result=await asyncio.to_thread(model.transcribe,audio); return result.get("text","").strip()
    async def speak(self,text:str)->bytes:
        if self.tts: return await self.tts(text)
        try: import pyttsx3
        except ImportError: raise RuntimeError("install pyttsx3 or provide a TTS adapter")
        def render():
            import tempfile
            engine=pyttsx3.init(); f=tempfile.NamedTemporaryFile(suffix=".wav",delete=False); f.close(); engine.save_to_file(text,f.name); engine.runAndWait(); return open(f.name,"rb").read()
        return await asyncio.to_thread(render)
    async def start_voice_session(self): return {"active":True}
    async def process_voice_input(self,audio:bytes)->dict:
        text=await self.transcribe(audio); response=await self.llm.complete([{"role":"user","content":text}]) if self.llm else text; return {"text":text,"response":response,"audio":await self.speak(response)}