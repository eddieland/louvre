import { useQuery } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'

import { Catalogue, NeedsDatabase } from '@/components/catalogue'
import { Header } from '@/components/header'
import { Notice } from '@/components/notice'
import { SignIn } from '@/components/sign-in'
import { Footer } from '@/components/site'
import { sessionQuery } from '@/lib/api'
import { catalogueSearch } from '@/lib/search'
import { usePageTitle } from '@/lib/title'

/** The catalogue: every artifact the reader reaches but the demo's, newest first (ui/DESIGN.md, "Catalogue"). */
export const Route = createFileRoute('/')({
    validateSearch: catalogueSearch,
    component: Home,
})

function Home() {
    const { origin, q } = Route.useSearch()
    const session = useQuery(sessionQuery)
    usePageTitle()
    return (
        <>
            <Header />
            <main>{body()}</main>
            <Footer />
        </>
    )

    function body() {
        if (!session.data) {
            return null
        }
        if (!session.data.configured) {
            return <NeedsDatabase />
        }
        const demo = session.data.demo ? (
            <p>
                The{' '}
                <Link to="/demo" className="link">
                    demo
                </Link>{' '}
                shows Louvre with pages already published, to anyone, without signing in.
            </p>
        ) : undefined
        if (session.data.account === null) {
            return (
                <Notice title="Sign in to read">
                    <p>Louvre holds the pages agents publish for people to read and comment on.</p>
                    {demo}
                    <SignIn />
                </Notice>
            )
        }
        return (
            <Catalogue
                origin={origin}
                query={q}
                title="Artifacts"
                after={demo}
                empty={
                    <Notice title="Nothing published yet">
                        <p>
                            Agents publish here through Louvre&rsquo;s MCP server. Mint a token for one on the{' '}
                            <Link to="/tokens" className="link">
                                Tokens
                            </Link>{' '}
                            page, and what it publishes appears here.
                        </p>
                        {demo}
                    </Notice>
                }
            />
        )
    }
}
