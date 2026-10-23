import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, download } from "../api";
import { Page } from "../components/Layout";
import { Icons } from "../components/icons";
import { ConfirmButton, Drawer, EntityCell, EntitySelect, FaTags, FocusPicker, Loading, NoScope } from "../components/ui";
import { useAuth } from "../lib/auth";
import { ago, bytes } from "../lib/format";
import { useToast } from "../lib/toast";
import { base, useDirectory, useEid, useEvidence, useModel, useMut, useWorkspace, type Model } from "../lib/workspace";
import type { Evidence } from "../types";

type LinkForm = { name: string; entity_id: number | null; doc_type: string; url: string; summary: string; focus_area_ids: number[] };

export function EvidencePage() {
  const eid = useEid();
  const ws = useWorkspace(eid);
  const m = useModel(ws.data);
  const evq = useEvidence(eid);
  const { canWrite } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const names = useDirectory();
  const [filter, setFilter] = useState<number | "all">("all");
  const [target, setTarget] = useState<number | null>(null);
  const [uploading, setUploading] = useState<string[]>([]);
  const [over, setOver] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [link, setLink] = useState<LinkForm | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const addLink = useMut(eid, (f: LinkForm) => api.post(`${base(eid)}/evidence/link`, f), { also: ["evidence"], success: "Evidence registered", onSuccess: () => setLink(null) });

  if (!ws.data || !evq.data) return <Page title="Evidence Library" eid={eid}><Loading /></Page>;
  const list = evq.data.filter((d) => m.inScope(filter, d.entity_id));
  const dest = target ?? (filter !== "all" ? filter : m.tree[0]?.e.id ?? null);

  const upload = async (files: File[]) => {
    if (!files.length) return;
    setUploading(files.map((f) => f.name));
    const fd = new FormData();
    if (dest != null) fd.append("entity_id", String(dest));
    files.forEach((f) => fd.append("files", f));
    try {
      const out = await api.upload<Evidence[]>(`${base(eid)}/evidence/upload`, fd);
      toast(out.length === 1 ? `${out[0].name}: mapped to ${out[0].focus_area_ids.length} focus areas` : `${out.length} files added and mapped`);
      for (const k of ["evidence", "ws", "activity"]) qc.invalidateQueries({ queryKey: [k, eid] });
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setUploading([]);
    }
  };

  return (
    <Page title="Evidence Library" sub="Artifacts, documents and tool exports, mapped to focus areas" eid={eid}>
      {!m.entities.length ? <NoScope eid={eid} /> : (
        <>
          <section className="row"><label className="lbl" htmlFor="docFilter">Entity</label><EntitySelect m={m} id="docFilter" value={filter} all onChange={(v) => setFilter(v as number | "all")} /></section>
          {canWrite && (
            <section className={`drop ${over ? "over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); upload([...e.dataTransfer.files]); }}>
              <div className="ic">{Icons.upload}</div>
              <div>
                <b>Add evidence</b>
                <p>Drop test strategies, execution results, defect exports, pipeline configs or reports (Word, Excel, PDF, CSV, text, YAML…). Each file is read, summarized and mapped to focus areas, and stored securely in this installation.</p>
                <div className="row" style={{ marginTop: 8 }}>
                  <label className="small muted" htmlFor="up-ent">For</label>
                  <EntitySelect m={m} id="up-ent" value={dest} onChange={(v) => setTarget(v as number | null)} />
                  <button className="btn sm" onClick={() => setLink({ name: "", entity_id: dest, doc_type: "", url: "", summary: "", focus_area_ids: [] })}>Register a link instead</button>
                </div>
              </div>
              <button className="btn primary" onClick={() => fileRef.current?.click()} disabled={uploading.length > 0}>Upload files</button>
              <input ref={fileRef} type="file" multiple hidden onChange={(e) => { const fs = [...(e.target.files || [])]; e.target.value = ""; upload(fs); }} />
            </section>
          )}
          {uploading.length > 0 && (
            <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {uploading.map((n) => <div key={n} className="prog"><span className="spin" /><div><b className="mono small">{n}</b><div className="small muted">Reading, classifying and mapping to focus areas…</div></div></div>)}
            </section>
          )}
          <section className="card">
            {list.length ? (
              <div className="tbl-wrap"><table>
                <thead><tr><th>Artifact</th><th>Entity</th><th>Type</th><th>Mapped focus areas</th><th>Added</th></tr></thead>
                <tbody>
                  {list.map((d) => (
                    <tr key={d.id} className="click" tabIndex={0} onClick={() => setOpenId(d.id)} onKeyDown={(e) => e.key === "Enter" && setOpenId(d.id)}>
                      <td><b className="small" style={{ wordBreak: "break-word" }}>{d.name}</b><div className="small muted" style={{ maxWidth: "46ch" }}>{d.summary.slice(0, 120)}{d.summary.length > 120 ? "…" : ""}</div></td>
                      <td><EntityCell m={m} id={d.entity_id} /></td>
                      <td><span className="badge">{d.doc_type}</span>{d.kind === "link" && <> <span className="badge">Link</span></>}</td>
                      <td><FaTags m={m} ids={d.focus_area_ids} /></td>
                      <td className="small muted" style={{ whiteSpace: "nowrap" }}>{ago(d.created_at)}{d.created_by && names.get(d.created_by) ? <><br />{names.get(d.created_by)}</> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            ) : <div className="empty"><b>No evidence{filter !== "all" ? " for this entity" : ""} yet</b><span>Upload the first artifact above.</span></div>}
          </section>
        </>
      )}
      {openId != null && <EvidenceDrawer key={openId} eid={eid} m={m} ev={evq.data.find((x) => x.id === openId)!} onClose={() => setOpenId(null)} />}
      {link && (
        <Drawer title="Register evidence" sub="For documents that live elsewhere (SharePoint, Confluence, Jira)" onClose={() => setLink(null)}
          footer={<><button className="btn" onClick={() => setLink(null)}>Cancel</button><button className="btn primary" disabled={!link.name.trim() || addLink.isPending} onClick={() => addLink.mutate(link)}>Add evidence</button></>}>
          <div className="fgrid">
            <div className="field full"><label htmlFor="ln-name">Title</label><input className="inp" id="ln-name" autoFocus value={link.name} onChange={(e) => setLink({ ...link, name: e.target.value })} placeholder="e.g. Reservations Test Strategy v3" /></div>
            <div className="field"><label htmlFor="ln-ent">Entity</label><EntitySelect m={m} id="ln-ent" value={link.entity_id} onChange={(v) => setLink({ ...link, entity_id: v as number | null })} style={{ width: "100%" }} /></div>
            <div className="field"><label htmlFor="ln-type">Type</label><input className="inp" id="ln-type" value={link.doc_type} onChange={(e) => setLink({ ...link, doc_type: e.target.value })} placeholder="e.g. Test strategy" /></div>
            <div className="field full"><label htmlFor="ln-url">Link</label><input className="inp" id="ln-url" value={link.url} onChange={(e) => setLink({ ...link, url: e.target.value })} placeholder="https://" /></div>
            <div className="field full"><label htmlFor="ln-sum">What it shows</label><textarea className="inp" id="ln-sum" value={link.summary} onChange={(e) => setLink({ ...link, summary: e.target.value })} placeholder="Key observations from this artifact" /></div>
            <div className="field full"><span className="lbl">Focus areas it evidences</span><FocusPicker m={m} value={link.focus_area_ids} onChange={(v) => setLink({ ...link, focus_area_ids: v })} /></div>
          </div>
        </Drawer>
      )}
    </Page>
  );
}

function EvidenceDrawer({ eid, m, ev, onClose }: { eid: number; m: Model; ev: Evidence; onClose: () => void }) {
  const { canWrite } = useAuth();
  const [fas, setFas] = useState(ev.focus_area_ids);
  const [entity, setEntity] = useState(ev.entity_id);
  const [summary, setSummary] = useState(ev.summary);
  const url = `${base(eid)}/evidence/${ev.id}`;
  const save = useMut(eid, () => api.patch(url, { focus_area_ids: fas, entity_id: entity, summary }), { also: ["evidence"], success: "Evidence updated", onSuccess: onClose });
  const del = useMut(eid, () => api.del(url), { also: ["evidence"], success: "Evidence removed", onSuccess: onClose });
  return (
    <Drawer wide title={ev.name} sub={`${m.path(ev.entity_id) || "No entity"} · added ${ago(ev.created_at)}`} onClose={onClose}
      footer={<>
        {canWrite && <span style={{ marginRight: "auto" }}><ConfirmButton label="Delete" onConfirm={() => del.mutate(undefined)} /></span>}
        <button className="btn" onClick={onClose}>Close</button>
        {canWrite && <button className="btn primary" onClick={() => save.mutate(undefined)} disabled={save.isPending}>Save</button>}
      </>}>
      <dl className="kv">
        <dt>Type</dt><dd>{ev.doc_type}</dd>
        {ev.size > 0 && <><dt>Size</dt><dd className="mono">{bytes(ev.size)}</dd></>}
        <dt>Classified by</dt><dd>{ev.classified_by === "rules" ? "Built-in analysis engine" : ev.classified_by === "manual" ? "Assessor" : ev.classified_by || "—"}</dd>
        {ev.has_file && <><dt>File</dt><dd><button className="btn sm" onClick={() => download(`${url}/file`)}>Download</button></dd></>}
        {ev.url && <><dt>Link</dt><dd>{/^https?:\/\//i.test(ev.url) ? <a href={ev.url} target="_blank" rel="noopener noreferrer">{ev.url}</a> : ev.url}</dd></>}
      </dl>
      <div className="field"><label htmlFor="ev-ent">Entity</label><EntitySelect m={m} id="ev-ent" value={entity} onChange={(v) => setEntity(v as number | null)} emptyLabel="Not set" style={{ width: "100%" }} /></div>
      <div className="field"><label htmlFor="ev-sum">Summary</label><textarea className="inp" id="ev-sum" disabled={!canWrite} value={summary} onChange={(e) => setSummary(e.target.value)} /></div>
      {ev.signals.length > 0 && <div><div className="eyebrow">Signals found in the file</div><ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{ev.signals.map((s, i) => <li key={i} className="small">{s}</li>)}</ul></div>}
      <div className="field"><span className="lbl">Mapped focus areas</span><FocusPicker m={m} value={fas} disabled={!canWrite} onChange={setFas} /></div>
    </Drawer>
  );
}
