type IconProps = {size?: number};

function Svg({size = 16, children}: IconProps & {children: React.ReactNode}) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{children}</svg>;
}

export function SearchIcon(props: IconProps) {
  return <Svg {...props}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></Svg>;
}

export function ExternalIcon(props: IconProps) {
  return <Svg {...props}><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></Svg>;
}

export function ArrowRightIcon(props: IconProps) {
  return <Svg {...props}><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></Svg>;
}

export function ArrowLeftIcon(props: IconProps) {
  return <Svg {...props}><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></Svg>;
}

export function FileIcon(props: IconProps) {
  return <Svg {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></Svg>;
}

export function RefreshIcon(props: IconProps) {
  return <Svg {...props}><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></Svg>;
}

export function LinkIcon(props: IconProps) {
  return <Svg {...props}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></Svg>;
}

export function InfoIcon(props: IconProps) {
  return <Svg {...props}><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></Svg>;
}

export function FilterIcon(props: IconProps) {
  return <Svg {...props}><path d="M22 3H2l8 9.46V19l4 2v-8.54z"/></Svg>;
}

export function AlertIcon(props: IconProps) {
  return <Svg {...props}><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></Svg>;
}
