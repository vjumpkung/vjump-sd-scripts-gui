// Scrollbars are transparent until their element scrolls (index.css). Marks the scrolling element
// with data-scrolling and clears the mark after a short idle.
const HIDE_DELAY_MS = 1_000

// Radix's scroll lock measures 0 for the page gutter when the page does not overflow, so the lock
// rule in index.css uses this width instead: the width of a scrollbar, exact at fractional zoom.
const setGutterWidth = () => {
    const probe = document.createElement('div')
    probe.style.cssText = 'position:fixed;top:0;width:100px;height:100px;overflow-y:scroll'
    const content = probe.appendChild(document.createElement('div'))
    document.body.append(probe)
    const width = 100 - content.getBoundingClientRect().width
    probe.remove()
    document.documentElement.style.setProperty('--scrollbar-gutter-width', `${width}px`)
}

export const initScrollbars = () => {
    setGutterWidth()
    window.addEventListener('resize', setGutterWidth)

    const timers = new WeakMap<Element, number>()

    document.addEventListener(
        'scroll',
        (event) => {
            const target = event.target === document ? document.documentElement : event.target
            if (!(target instanceof Element)) return
            if (!target.hasAttribute('data-scrolling')) target.setAttribute('data-scrolling', '')
            window.clearTimeout(timers.get(target))
            timers.set(
                target,
                window.setTimeout(() => {
                    target.removeAttribute('data-scrolling')
                    timers.delete(target)
                }, HIDE_DELAY_MS)
            )
        },
        { capture: true, passive: true }
    )
}
