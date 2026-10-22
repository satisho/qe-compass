import type { ReactElement } from "react";

const s = { fill: "none", stroke: "currentColor", strokeWidth: 1.8 } as const;

export const Icons: Record<string, ReactElement> = {
  overview: (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="9" /><path d="M14.5 9.5 11 11l-1.5 3.5L13 13z" fill="currentColor" /></svg>),
  scope: (<svg viewBox="0 0 24 24" {...s}><rect x="3" y="4" width="7" height="7" rx="1.5" /><rect x="14" y="4" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><path d="M17.5 14v7M14 17.5h7" /></svg>),
  framework: (<svg viewBox="0 0 24 24" {...s}><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="2" fill="currentColor" /><circle cx="15" cy="12" r="2" fill="currentColor" /><circle cx="10" cy="18" r="2" fill="currentColor" /></svg>),
  interviews: (<svg viewBox="0 0 24 24" {...s}><path d="M4 5h11v8H9l-4 3v-3H4z" /><path d="M15 9h5v8h-1v3l-4-3h-4v-2" /></svg>),
  evidence: (<svg viewBox="0 0 24 24" {...s}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></svg>),
  assessment: (<svg viewBox="0 0 24 24" {...s}><path d="M9 4h6l1 2h3v14H5V6h3z" /><path d="M8.5 13l2.5 2.5 4.5-5" /></svg>),
  analyst: (<svg viewBox="0 0 24 24" {...s}><path d="M12 3l1.8 4.6L18.5 9l-4.7 1.6L12 15l-1.8-4.4L5.5 9l4.7-1.4z" /><path d="M18 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" /></svg>),
  heatmap: (<svg viewBox="0 0 24 24" {...s}><rect x="3" y="3" width="5" height="5" rx="1" /><rect x="9.5" y="3" width="5" height="5" rx="1" fill="currentColor" /><rect x="16" y="3" width="5" height="5" rx="1" /><rect x="3" y="9.5" width="5" height="5" rx="1" fill="currentColor" /><rect x="9.5" y="9.5" width="5" height="5" rx="1" /><rect x="16" y="9.5" width="5" height="5" rx="1" fill="currentColor" /><rect x="3" y="16" width="5" height="5" rx="1" /><rect x="9.5" y="16" width="5" height="5" rx="1" fill="currentColor" /><rect x="16" y="16" width="5" height="5" rx="1" /></svg>),
  report: (<svg viewBox="0 0 24 24" {...s}><path d="M6 3h9l4 4v14H6z" /><path d="M9 17v-3M12 17v-6M15 17v-4" /></svg>),
  engagements: (<svg viewBox="0 0 24 24" {...s}><rect x="3" y="5" width="18" height="15" rx="2" /><path d="M8 5V3h8v2M3 11h18" /></svg>),
  users: (<svg viewBox="0 0 24 24" {...s}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5" /><circle cx="17" cy="9" r="2.5" /><path d="M16 14.6c2.6.2 4.6 1.9 5.3 4.9" /></svg>),
  account: (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4.2 4.1-6.5 8-6.5s7 2.3 8 6.5" /></svg>),
  spark: (<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" /></svg>),
  upload: (<svg width="22" height="22" viewBox="0 0 24 24" {...s}><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v4h16v-4" /></svg>),
  doc: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 3h8l4 4v14H6z" /></svg>),
  talk: (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 5h16v11H9l-5 4z" /></svg>),
};

export function Compass({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <circle cx="17" cy="17" r="15" fill="none" stroke="#3bb4c9" strokeWidth="1.6" />
      <circle cx="17" cy="17" r="10.5" fill="none" stroke="#3bb4c9" strokeOpacity=".35" />
      <path d="M17 4.5 L20.2 17 L17 29.5 L13.8 17Z" fill="#fff" />
      <path d="M17 4.5 L20.2 17 L13.8 17Z" fill="#3bb4c9" />
      <circle cx="17" cy="17" r="1.8" fill="#0b2a55" />
    </svg>
  );
}

export function Spark({ size = 15 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" /></svg>;
}
