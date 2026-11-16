const paths = {
  search: 'M21 21l-4.3-4.3M19 11a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  arrow: 'M4 12h15m-6-6 6 6-6 6',
  back: 'M20 12H5m6-6-6 6 6 6',
  external: 'M13 5h6v6m0-6-9 9M9 6H5v13h13v-4',
  left: 'm15 18-6-6 6-6',
  right: 'm9 18 6-6-6-6',
  close: 'm6 6 12 12M18 6 6 18',
  filter: 'M3 4h18l-7 8v6l-4 2v-8L3 4Z',
  down: 'm6 9 6 6 6-6',
  check: 'm5 12 4 4L19 6',
  tag: 'M3 4h8l10 10-7 7L3 10V4Zm4 4h.01',
  spark: 'M12 2v5m0 10v5M3.3 7l4.3 2.5m8.8 5 4.3 2.5M3.3 17l4.3-2.5m8.8-5L20.7 7',
  trend: 'm3 17 6-6 4 4 7-8m-5 0h5v5',
  percent: 'M5 19 19 5M9 7a2 2 0 1 1-4 0 2 2 0 0 1 4 0Zm10 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
  clock: 'M12 7v5l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  image: 'M4 5h16v14H4zM4 16l4-4 4 4 3-3 5 5M15 9h.01',
}

export default function Icon({ name }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name]} />
    </svg>
  )
}
