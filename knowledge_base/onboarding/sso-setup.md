# SSO setup

We support SAML 2.0 and OIDC. The customer's IT admin configures the IdP side
and shares the metadata URL with us. On the support side we only need the
metadata URL and the domain to claim.

## Gotchas
- Email attribute must map to `email`, not `mail`. Okta defaults to `email`
  but Azure AD defaults vary by tenant.
- The first SSO login creates the user account. Customers who are already
  invited by email before SSO is enabled need to log in through SSO at least
  once before their old password stops working.
- Break-glass admin accounts should always use password + MFA, not SSO, so
  the customer is not locked out if the IdP goes down.
