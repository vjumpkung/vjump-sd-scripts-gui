import { API_BASE_URL } from './client'
import type { ClientToServerEvents, InvalidateEvent, ServerToClientEvents } from './types'
import { type Socket, io } from 'socket.io-client'

// A base URL with a path prefix handed to io() would become a namespace, so only the origin goes
// in and the prefix goes into `path`. No `withCredentials`: same-origin requests send the cookie.
const base = new URL(API_BASE_URL || '/', location.href)

export const realtimeSocket: Socket<ServerToClientEvents, ClientToServerEvents> = io(base.origin, {
    path: `${base.pathname.replace(/\/$/, '')}/api/socket.io`,
    autoConnect: false
})

export const onInvalidate = (handler: (event: InvalidateEvent) => void) => {
    realtimeSocket.on('invalidate', handler)
    return () => {
        realtimeSocket.off('invalidate', handler)
    }
}

export const onRealtimeConnect = (handler: () => void) => {
    realtimeSocket.on('connect', handler)
    return () => {
        realtimeSocket.off('connect', handler)
    }
}

export const onRealtimeDisconnect = (handler: (reason: Socket.DisconnectReason) => void) => {
    realtimeSocket.on('disconnect', handler)
    return () => {
        realtimeSocket.off('disconnect', handler)
    }
}

// The server only streams `system_resources` to sockets that asked for it, so it is reference
// counted: the first user subscribes and the last one unsubscribes.
let resourceUsers = 0

// Subscriptions do not survive a reconnect.
realtimeSocket.on('connect', () => {
    if (resourceUsers > 0) realtimeSocket.emit('subscribe', 'resources')
})

export const retainResources = () => {
    resourceUsers += 1
    if (resourceUsers === 1 && realtimeSocket.connected) {
        realtimeSocket.emit('subscribe', 'resources')
    }
    let released = false
    return () => {
        if (released) return
        released = true
        resourceUsers -= 1
        if (resourceUsers === 0 && realtimeSocket.connected) {
            realtimeSocket.emit('unsubscribe', 'resources')
        }
    }
}
