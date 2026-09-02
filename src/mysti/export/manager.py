from __future__ import annotations
import csv,io,json,inspect
class ExportManager:
    def __init__(self,memory_provider=None,conversation_provider=None,graph_provider=None): self.providers={"memories":memory_provider,"conversations":conversation_provider,"graph":graph_provider}
    async def _data(self,key):
        p=self.providers[key]; value=p() if p else []; return await value if inspect.isawaitable(value) else value
    def _format(self,data,format):
        if format=="json":return json.dumps(data,indent=2,default=str)
        if format=="markdown":return "\n".join(f"- {x}" if not isinstance(x,dict) else "- "+str(x.get("content",x.get("title",x))) for x in data)
        if format=="csv":
            rows=data if isinstance(data,list) else [data]; fields=sorted({k for r in rows if isinstance(r,dict) for k in r}); out=io.StringIO(); w=csv.DictWriter(out,fieldnames=fields); w.writeheader(); w.writerows(rows); return out.getvalue()
        raise ValueError("format must be json, csv, or markdown")
    async def export_memories(self,format="json"):return self._format(await self._data("memories"),format)
    async def export_conversations(self,format="json"):return self._format(await self._data("conversations"),format)
    async def export_knowledge_graph(self,format="json"):return self._format(await self._data("graph"),format)
    async def export_all(self,format="json"):return self._format({k:await self._data(k) for k in self.providers},format)