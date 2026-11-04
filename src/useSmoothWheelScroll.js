import { useEffect } from 'react'

const FRICTION = 0.94
const ACCELERATION = 0.2
const SCROLL_MULTIPLIER = 0.06
const STOP_THRESHOLD = 0.25

function useSmoothWheelScroll() {
  useEffect(() => {
    const root = document.documentElement
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const previousScrollBehavior = root.style.scrollBehavior
    let currentY = window.scrollY
    let velocity = 0
    let targetVelocity = 0
    let frameId = null
    let horizontalCarousel = null
    let horizontalPosition = 0
    let horizontalVelocity = 0
    let horizontalTargetVelocity = 0
    let horizontalFrameId = null
    let previousCarouselBehavior = ''

    const stopAnimation = () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId)
      frameId = null
      velocity = 0
      targetVelocity = 0
      currentY = window.scrollY
      root.style.scrollBehavior = previousScrollBehavior
    }

    const animate = () => {
      targetVelocity *= FRICTION
      velocity += (targetVelocity - velocity) * ACCELERATION
      currentY += velocity

      const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight)
      currentY = Math.max(0, Math.min(currentY, maxScroll))
      if (currentY === 0 || currentY === maxScroll) {
        velocity = 0
        targetVelocity = 0
      }

      // Use direct frame-by-frame movement while the custom easing is active.
      root.style.scrollBehavior = 'auto'
      window.scrollTo(0, currentY)

      if (Math.abs(velocity) > STOP_THRESHOLD || Math.abs(targetVelocity) > STOP_THRESHOLD) {
        frameId = window.requestAnimationFrame(animate)
      } else {
        frameId = null
        velocity = 0
        targetVelocity = 0
        currentY = window.scrollY
        root.style.scrollBehavior = previousScrollBehavior
      }
    }

    const stopHorizontalAnimation = () => {
      if (horizontalFrameId !== null) window.cancelAnimationFrame(horizontalFrameId)
      if (horizontalCarousel) horizontalCarousel.style.scrollBehavior = previousCarouselBehavior
      horizontalFrameId = null
      horizontalCarousel = null
      horizontalVelocity = 0
      horizontalTargetVelocity = 0
    }

    const animateHorizontal = () => {
      if (!horizontalCarousel) return

      horizontalTargetVelocity *= FRICTION
      horizontalVelocity += (horizontalTargetVelocity - horizontalVelocity) * ACCELERATION
      horizontalPosition += horizontalVelocity

      const maxScroll = Math.max(0, horizontalCarousel.scrollWidth - horizontalCarousel.clientWidth)
      horizontalPosition = Math.max(0, Math.min(horizontalPosition, maxScroll))
      if (horizontalPosition === 0 || horizontalPosition === maxScroll) {
        horizontalVelocity = 0
        horizontalTargetVelocity = 0
      }

      horizontalCarousel.style.scrollBehavior = 'auto'
      horizontalCarousel.scrollLeft = horizontalPosition

      if (Math.abs(horizontalVelocity) > STOP_THRESHOLD || Math.abs(horizontalTargetVelocity) > STOP_THRESHOLD) {
        horizontalFrameId = window.requestAnimationFrame(animateHorizontal)
      } else {
        horizontalFrameId = null
        horizontalVelocity = 0
        horizontalTargetVelocity = 0
        horizontalPosition = horizontalCarousel.scrollLeft
        horizontalCarousel.style.scrollBehavior = previousCarouselBehavior
      }
    }

    const onWheel = (event) => {
      if (motionPreference.matches || event.ctrlKey || event.metaKey) return
      if (event.target instanceof Element) {
        if (event.target.closest('[data-scroll-lock]')) {
          event.preventDefault()
          return
        }
        if (event.target.closest('textarea, select, input[type="number"], input[type="range"], [contenteditable="true"]')) return
      }

      const carousel = event.target instanceof Element ? event.target.closest('.scrollbar-hide') : null
      const isHorizontalGesture = event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)
      if (isHorizontalGesture) {
        if (!carousel || carousel.scrollWidth <= carousel.clientWidth) return
        event.preventDefault()

        if (horizontalCarousel !== carousel) {
          stopHorizontalAnimation()
          horizontalCarousel = carousel
          horizontalPosition = carousel.scrollLeft
          previousCarouselBehavior = carousel.style.scrollBehavior
        } else if (horizontalFrameId === null) {
          horizontalPosition = carousel.scrollLeft
        }

        const multiplier = event.deltaMode === WheelEvent.DOM_DELTA_LINE
          ? 16
          : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
            ? carousel.clientWidth
            : 1
        const horizontalDelta = event.shiftKey ? event.deltaY : event.deltaX
        horizontalTargetVelocity = Math.max(-1200, Math.min(1200, horizontalTargetVelocity + horizontalDelta * multiplier * SCROLL_MULTIPLIER))
        if (horizontalFrameId === null) horizontalFrameId = window.requestAnimationFrame(animateHorizontal)
        return
      }

      event.preventDefault()
      const multiplier = event.deltaMode === WheelEvent.DOM_DELTA_LINE
        ? 16
        : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
          ? window.innerHeight
          : 1
      const delta = event.deltaY * multiplier

      if (frameId === null) currentY = window.scrollY
      targetVelocity = Math.max(-1200, Math.min(1200, targetVelocity + delta * SCROLL_MULTIPLIER))
      if (frameId === null) frameId = window.requestAnimationFrame(animate)
    }

    const cancelSmoothScroll = () => {
      stopAnimation()
      stopHorizontalAnimation()
    }

    const resetScroll = () => {
      cancelSmoothScroll()
      window.scrollTo({ top: 0, behavior: motionPreference.matches ? 'auto' : 'smooth' })
    }

    window.addEventListener('wheel', onWheel, { passive: false })
    window.cancelSmoothScroll = cancelSmoothScroll
    window.resetScroll = resetScroll

    return () => {
      window.removeEventListener('wheel', onWheel)
      stopAnimation()
      stopHorizontalAnimation()
      delete window.cancelSmoothScroll
      delete window.resetScroll
    }
  }, [])
}

export default useSmoothWheelScroll
