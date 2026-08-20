import { useState } from 'react';
import { signIn, confirmSignIn } from 'aws-amplify/auth';

function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  // For forcing password changes
  const [needsNewPassword, setNeedsNewPassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Show password toggle
  const [showPassword, setShowPassword] = useState(false);

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (needsNewPassword && newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      if (needsNewPassword) {
        // Complete the "Force Password Change" challenge
        const { isSignedIn, nextStep } = await confirmSignIn({
          challengeResponse: newPassword
        });
        
        if (isSignedIn) {
          onLogin();
        } else {
          setError(`Additional authentication required: ${nextStep.signInStep}`);
        }
      } else {
        // Normal Sign In
        const { isSignedIn, nextStep } = await signIn({
          username: email,
          password: password,
        });

        if (isSignedIn) {
          onLogin();
        } else if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
          // AWS requires a permanent password change!
          setNeedsNewPassword(true);
        } else {
          setError(`Additional authentication required: ${nextStep.signInStep}`);
        }
      }
    } catch (error) {
      console.error('Login error:', error);
      setError(error.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">

        <div className="login-header">
          <h1>{needsNewPassword ? "Update Password" : "Welcome to CampusPulse"}</h1>
          <p>{needsNewPassword ? "AWS requires you to update your password." : "Sign in to your account"}</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>

          {!needsNewPassword ? (
            <>
              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>
            </>
          ) : (
            <>
              <div className="form-group">
                <label htmlFor="new-password">New Password</label>
                <input
                  id="new-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter a strong password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="confirm-password">Confirm Password</label>
                <input
                  id="confirm-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Confirm your password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                />
              </div>
            </>
          )}

          <div style={{ display: 'flex', alignItems: 'center', marginTop: '5px' }}>
            <input 
              type="checkbox" 
              id="show-password" 
              checked={showPassword} 
              onChange={() => setShowPassword(!showPassword)} 
              style={{ marginRight: '8px', cursor: 'pointer' }}
            />
            <label htmlFor="show-password" style={{ fontSize: '0.85rem', color: '#a0aec0', cursor: 'pointer' }}>Show Password</label>
          </div>

          {error && (
            <p style={{ color: '#f87171', fontSize: '0.9rem', marginTop: '5px' }}>
              {error}
            </p>
          )}

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? 'Authenticating...' : (needsNewPassword ? 'Set Password & Login' : 'Sign In')}
          </button>

        </form>

      </div>
    </div>
  );
}

export default Login;
