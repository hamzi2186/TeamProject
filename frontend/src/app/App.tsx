import { Navigate, Route, Routes } from "react-router-dom";
import { AuthPage } from "../auth/AuthPage";

function PlaceholderDashboard() {
  const token = sessionStorage.getItem("trex_access_token");
  if (!token) return <Navigate to="/auth/login" replace />;
  return <main className="placeholder"><div className="brand-mark">T</div><h1>T Rex foundation is ready</h1><p>Shared authentication is connected. Product modules follow in the next phases.</p></main>;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<PlaceholderDashboard />} />
      <Route path="/auth/login" element={<AuthPage mode="login" />} />
      <Route path="/auth/register" element={<AuthPage mode="register" />} />
      <Route path="/auth/verify-email" element={<AuthPage mode="verify" />} />
      <Route path="/auth/forgot-password" element={<AuthPage mode="forgot" />} />
      <Route path="/auth/reset-password" element={<AuthPage mode="reset" />} />
      <Route path="*" element={<Navigate to="/auth/login" replace />} />
    </Routes>
  );
}
