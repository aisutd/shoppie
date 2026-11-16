import Icon from './Icon.jsx'

export default function Tabs({ id, label, items, selected, onSelect }) {
  function moveFocus(event, index) {
    let next
    if (event.key === 'ArrowRight') next = (index + 1) % items.length
    else if (event.key === 'ArrowLeft') next = (index - 1 + items.length) % items.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = items.length - 1
    else return
    event.preventDefault()
    event.currentTarget.parentElement.children[next].focus()
    onSelect(items[next].id)
  }

  return (
    <div className="tab-strip" role="tablist" aria-label={label}>
      {items.map((item, index) => (
        <button key={item.id} id={`${id}-tab-${item.id}`} type="button" role="tab"
          aria-selected={selected === item.id} tabIndex={selected === item.id ? 0 : -1}
          aria-controls={`${id}-panel-${item.id}`} onKeyDown={event => moveFocus(event, index)}
          onClick={() => onSelect(item.id)}>
          {item.icon && <Icon name={item.icon} />} {item.label}
          {item.count != null && <span className="tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  )
}
