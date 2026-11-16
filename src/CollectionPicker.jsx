import { useEffect, useRef, useState } from 'react'
import Icon from './Icon.jsx'

export default function CollectionPicker({ items, selected, onSelect, isActive }) {
  const [open, setOpen] = useState(false)
  const picker = useRef(null)
  const trigger = useRef(null)

  useEffect(() => {
    if (!isActive) setOpen(false)
    if (!isActive || !open) return
    function closeOutside(event) {
      if (!picker.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [isActive, open])

  function closeWithFocus() {
    setOpen(false)
    trigger.current?.focus()
  }

  return (
    <div className="collection-picker" ref={picker}
      onBlur={event => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) setOpen(false) }}
      onKeyDown={event => {
        if (open && event.key === 'Escape') {
          event.preventDefault()
          closeWithFocus()
        }
      }}>
      <button type="button" className="collection-picker-trigger" ref={trigger}
        aria-expanded={open} aria-controls="discover-collections" onClick={() => setOpen(!open)}>
        <Icon name="filter" /> Filter &amp; Sort <Icon name="down" />
      </button>
      <ul className="collection-picker-options" id="discover-collections" aria-label="Discover collections" hidden={!open}>
        {items.map(item => (
          <li key={item.id}>
            <button type="button" aria-pressed={item.id === selected} onClick={() => {
              onSelect(item.id)
              closeWithFocus()
            }}>
              <Icon name={item.icon} /> <span>{item.label}</span> {item.id === selected && <Icon name="check" />}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
