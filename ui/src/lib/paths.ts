// Where a person may be sent back to after signing in: a page of Louvre's own, as louvre.web.auth.local_path decides.

/**
 * Keep a path to come back to only if it is a page on this host, and not under /auth; anything else reads as the
 * catalogue. A browser reads a backslash as a slash and drops tabs and newlines, so either could make `//host`.
 */
export function localPath(given: unknown): string {
    if (typeof given !== 'string' || !given.startsWith('/') || given.startsWith('//') || /[\\\p{Cc}]/u.test(given)) {
        return '/'
    }
    const [path = ''] = given.split(/[?#]/u, 1)
    return path === '/auth' || path.startsWith('/auth/') ? '/' : given
}
