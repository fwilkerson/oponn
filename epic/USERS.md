# Users

To this point the ballot dashboard is wide open. Any ballot created by any user can be viewed. This is a blocking issue for deploying the appliation. We need to add a user layer, attributing ballot creation to users, while still keeping voting anonymous (not requiring account creation to vote on a ballot). In a similar vane, URLs currently contain the id of the ballot itself, meaning ballot ids are easily guessable, this needs to change.

## Story 1: Modern & Secure Identity
*   **As a** ballot creator, **I want** to sign in using my existing Google or Apple account **so that** I don't have to remember another password or trust a new site with my credentials.
*   **As a** developer, **I want** to use industry-standard OAuth2 flows **so that** we avoid the risks of storing sensitive password hashes.

## Story 2: Non-Guessable & Private Links
*   **As a** user, **I want** ballot URLs to use unique, random identifiers (UUIDs) **so that** strangers cannot guess the ID of my private poll just by incrementing a number.

## Story 3: Unified User Dashboard
*   **As a** signed-in user, **I want** to see a dashboard listing all ballots I have created **so that** I can easily check results or share links again.

## Story 4: Ballot Attribution
*   **As a** logged-in user, **I want** ballots I create to be automatically linked to my account.
*   **As a** guest (anonymous user), **I can** still create ballots, but I am responsible for saving the links myself.

## Story 5: Voting Integrity
*   **As a** ballot creator, **I want** reasonable assurance that people are voting only once per device **so that** my poll results aren't easily spammed. (Implementation: Signed Cookies).