// Jednoduché ikonky (1.6px ťah, zladené s písmom Inter)
import type { JSX } from "preact";

const Svg = (props: JSX.SVGAttributes<SVGSVGElement> & { children: JSX.Element | JSX.Element[] }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" {...props} />
);

export const Plane = () => <Svg><path d="M10.5 13.5 3 11l1.6-1.6 7.4.9 4.4-4.4a2.1 2.1 0 0 1 3 3L15 13.3l.9 7.4L14.3 22l-2.5-7.5-3 3V20l-1.6 1.2-1-3.2-3.2-1L4.2 15.4h2.5z" /></Svg>;
export const Ticket = () => <Svg><path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4z" /><path d="M14 6v12" stroke-dasharray="2 2.5" /></Svg>;
export const Bulb = () => <Svg><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3z" /></Svg>;
export const Chart = () => <Svg><path d="M4 19V5M4 19h16M8 15l3.5-4 3 2.5L20 7" /></Svg>;
export const Gear = () => <Svg><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></Svg>;
export const Close = () => <Svg><path d="M6 6l12 12M18 6 6 18" /></Svg>;
export const External = () => <Svg><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></Svg>;
export const Bell = () => <Svg><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10.3 21a1.9 1.9 0 0 0 3.4 0" /></Svg>;
export const Ban = () => <Svg><circle cx="12" cy="12" r="9" /><path d="m5.6 5.6 12.8 12.8" /></Svg>;
export const Arrow = () => <Svg><path d="M5 12h14M13 6l6 6-6 6" /></Svg>;
export const Refresh = () => <Svg><path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4" /></Svg>;
export const Info = () => <Svg><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></Svg>;
