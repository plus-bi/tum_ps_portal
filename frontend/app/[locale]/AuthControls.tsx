"use client";

import {SignedIn, SignedOut, SignInButton, SignUpButton, UserButton} from "@clerk/nextjs";

export default function AuthControls() {
  return <div className="auth-controls">
    <SignedOut>
      <SignInButton mode="modal"><button className="auth-button" type="button">Sign in</button></SignInButton>
      <SignUpButton mode="modal"><button className="auth-button auth-button-primary" type="button">Create account</button></SignUpButton>
    </SignedOut>
    <SignedIn><UserButton afterSignOutUrl="/en"/></SignedIn>
  </div>;
}
