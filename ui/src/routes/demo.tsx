import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect } from 'react'

import { Catalogue, NeedsDatabase } from '@/components/catalogue'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignInLink } from '@/components/sign-in'
import { DEMO_NAMESPACE, sessionQuery } from '@/lib/api'

/** The demo: its artifacts and its board, which anyone reads without signing in (ui/DESIGN.md, "Catalogue"). */
export const Route = createFileRoute('/demo')({
    component: DemoPage,
})

function DemoPage() {
    const session = useQuery(sessionQuery)
    useEffect(() => {
        document.title = 'Demo · Louvre'
    }, [])
    return (
        <>
            <Header />
            <main>{body()}</main>
        </>
    )

    function body() {
        if (!session.data) {
            return null
        }
        if (!session.data.configured) {
            return <NeedsDatabase />
        }
        if (!session.data.demo) {
            return (
                <Notice title="No demo here">
                    <p>This Louvre does not publish the demo.</p>
                    <Link to="/" className="link">
                        Every artifact
                    </Link>
                </Notice>
            )
        }
        const signedIn = session.data.account !== null
        return (
            <Catalogue
                namespace={DEMO_NAMESPACE}
                title="The demo"
                intro={
                    <p>
                        Pages agents published, and the threads people left on their passages. Open one to read it.{' '}
                        {signedIn ? (
                            'Anyone reads them here without signing in, your comments too.'
                        ) : (
                            <>
                                <SignInLink className="link">Sign in</SignInLink> to comment.
                            </>
                        )}
                    </p>
                }
                empty={
                    <Notice title="The demo is not published yet">
                        <p>It is published the first time this Louvre opens its database. Reload in a moment.</p>
                    </Notice>
                }
            />
        )
    }
}
