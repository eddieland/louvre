import { createFileRoute } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'
import { Footer } from '@/components/site'
import { localPath } from '@/lib/paths'
import { usePageTitle } from '@/lib/title'

/** What the sign-in page is told: why the last try came back unfinished, and the page to return to. */
interface SignInSearch {
    /** Why GitHub's sign-in came back unfinished, as the server says it. */
    sign_in?: string
    /** The page to return to once signed in. */
    next?: string
}

/** Signing in, on a page of its own. */
export const Route = createFileRoute('/sign-in')({
    validateSearch: (search: Record<string, unknown>): SignInSearch => ({
        ...(typeof search['sign_in'] === 'string' ? { sign_in: search['sign_in'] } : {}),
        ...(localPath(search['next']) === '/' ? {} : { next: localPath(search['next']) }),
    }),
    component: SignInPage,
})

function SignInPage() {
    const { sign_in: why, next } = Route.useSearch()
    usePageTitle('Sign in')
    return (
        <>
            <Header />
            <main>
                <Notice title="Sign in">
                    <p>Sign in to comment on artifacts and to mint tokens for your agents.</p>
                    <SignIn why={why} next={next ?? '/'} />
                </Notice>
            </main>
            <Footer />
        </>
    )
}
