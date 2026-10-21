# ADR-03: Authentication with Clerk

Status: Proposed. The TL and PO must approve it before the merge into `main`.
Tasks: E2.1 (#18), E2.2 (#19), E2.7 (#24).

## Context

The API used one shared key (`CDSS_API_KEYS`).
The frontend sent this key as `VITE_API_KEY`, so the key was in the public JS bundle.
It did not identify the doctor.
The base plan (Lab 2) was our own OAuth2/JWT with bcrypt password hashes in PostgreSQL.
PostgreSQL (E3.1) is not ready yet.

## Decision

We use Clerk for sign-in and user management.

- Clerk stores the users and the password hashes. We do not store passwords.
- Sign-up is invite-only (Clerk access mode "Invite-only"). An admin invites a doctor in the Clerk Dashboard.
- The role (`doctor` or `admin`) is in the user's public metadata. Only the server or an admin can change it.
- A session token template adds the claim `"role": "{{user.public_metadata.role}}"`.
- The frontend (`@clerk/react`) shows the Clerk sign-in form and sends the session token as `Authorization: Bearer`.
- The API checks each token: RS256 signature against the Clerk JWKS, `exp`, `nbf`, `iss` (`CLERK_ISSUER`), and `azp` (our frontend origins).
- The API does not call Clerk for each request. It caches the JWKS keys.
- There is no users table. Other tables (ownership in E2.4, audit log in E2.5) keep the Clerk user ID (`sub`) as a string.

## How this meets the acceptance criteria

| Criterion | How |
| --- | --- |
| E2.1: user has a unique ID and a role | Clerk user ID (`user_…`) and the `role` claim |
| E2.1: passwords only as a hash (bcrypt or an approved provider mechanism) | Clerk stores the password hashes. This ADR approves it. |
| E2.2: missing, invalid or expired token gives 401 | `get_current_user` in `api/src/api/dependencies.py`, tests in `api/tests/test_auth.py` |
| E2.2: health is public | `/api/v1/health` has no auth dependency. There is no login endpoint, because Clerk does the sign-in. |
| E2.2: session of 30 minutes | Clerk session tokens live 60 seconds. The frontend signs the user out after 30 minutes without input (`useIdleSignOut`). |
| E2.2: production does not start without access settings | `create_app` stops when `CLERK_ISSUER` is empty. |
| E2.2: shared `VITE_API_KEY` is not the authorization | `VITE_API_KEY` and `CDSS_API_KEYS` are removed. |
| E2.3: the server sets the role | Public metadata cannot be changed from the browser. A user without a role gets 403. |

## Consequences

- Clerk's own inactivity timeout and maximum lifetime settings need the paid plan. We use the frontend idle timer instead. The Clerk session (7 days on the free plan) stays active if the browser tab stays open with activity.
- The production Clerk instance needs DNS records on `notetaker.uk` and its own Google OAuth client, if Google sign-in is used.
- Patient data does not go to Clerk. Clerk has only the doctor's email and name.
- To change the provider later, replace the frontend SDK and the token check. The rest of the API uses only `CurrentUser`.

## Alternatives

- Own OAuth2/JWT with bcrypt: more code (login, password reset, invites) and it needs PostgreSQL first.
- Keep the shared API key: it does not identify the doctor, so it does not meet E2.2.
