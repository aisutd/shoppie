import Icon from './Icon.jsx'

export default function PageBackLink({ to, navigate }) {
  return (
    <footer className="page-footer">
      <a className="page-back-link" href={to} onClick={event => navigate(to, event)}>
        <Icon name="back" /> Back to {to === '/discover' ? 'Discover' : 'Home'}
      </a>
    </footer>
  )
}
