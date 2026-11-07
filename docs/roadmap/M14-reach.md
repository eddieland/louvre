# M14. Reaching people away from Louvre

REQUIREMENTS U11 (its gap), U7, C1, L7, D009, D010. A reply to a person's comment, or a decision that asks them, finds
them where they are, so the loop does not wait on someone opening Louvre.

- A person says where to reach them, on a page of their own beside Tokens: an email address, confirmed by a link
  Louvre sends to it, and nothing until it is confirmed. Other channels (a chat tool's incoming webhook, say) wait on
  someone asking for one.
- What is sent is what their inbox would show them (U11): a reply to their comment, a thread of theirs resolved, a new
  version of an artifact they take part in, or a decision that asks them, quoting the words, with a link that opens
  the page where the inbox would. One message per artifact until they open it: the inbox already knows what they have
  read, so a flurry of replies is one message, and their own words and their own agents' are never sent to them.
- Sent from the write that causes it, after its commit, since Louvre runs stateless and keeps no worker (D010). A
  send that fails never fails the write, and is logged.
- A message is text: the quote, the title, the link, and where to turn it off (their page). Never the artifact's
  HTML, and nothing that acts: no reply by email, no link that writes (D009, L7).
- The deployment names the sender in its environment (docs/DEPLOY.md), by SMTP from the stdlib first; without one
  nothing is sent, and the page says so.
- C1 holds: this reaches people, never readers of the feed; canopy still pulls.

Accept: the operator, as one person, comments on an artifact; an agent replies, and a second person's reply lands
before the first opens Louvre: one email, quoting the agent's words, whose link opens the thread. A decision that
asks them reaches them the same way. Nothing is sent to a person who gave no address.

Status: proposed 2026-11-07, for the operator to order or strike; not started.
