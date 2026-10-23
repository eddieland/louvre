import { createFileRoute } from '@tanstack/react-router'

import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'

/** Signing in, on a page of its own. */
export const Route = createFileRoute('/sign-in')({
    component: SignInPage,
})

function SignInPage() {
    return (
        <>
            <Header />
            <main>
                <Notice title="Sign in">
                    <p>Sign in to comment on artifacts and to mint tokens for your agents.</p>
                    <SignIn />
                </Notice>
            </main>
        </>
    )
}
