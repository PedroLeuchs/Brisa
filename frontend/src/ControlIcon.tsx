export function ControlIcon({kind}:{kind:'mode'|'fan'|'functions'|'timer'}){
  const paths={mode:<><rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/></>,fan:<><circle cx="12" cy="12" r="2"/><path d="M10 10C3 5 11 1 12 5v5m2 0c5-7 9 1 5 2h-5m0 2c7 5-1 9-2 5v-5m-2 0c-5 7-9-1-5-2h5"/></>,functions:<><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/></>,timer:<><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/></>};
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind]}</svg>;
}

export function PowerIcon(){
  return <svg className="power-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true" focusable="false">
    <path d="M12 3v9"/><path d="M7.1 5.8a8 8 0 1 0 9.8 0"/>
  </svg>;
}
