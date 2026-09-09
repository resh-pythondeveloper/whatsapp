import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MailCheck, ArrowLeft } from "lucide-react";
import api from "../services/api";

function VerifyEmail() {
  const navigate = useNavigate();

  const email = sessionStorage.getItem("verification_email");

  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleOtpChange = (event) => {
    const value = event.target.value.replace(/\D/g, "");

    if (value.length <= 6) {
      setOtp(value);
    }

    setError("");
    setSuccess("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!email) {
      setError("Verification email not found. Please register again.");
      return;
    }

    if (otp.length !== 6) {
      setError("Please enter a valid 6-digit OTP.");
      return;
    }

    try {
      setLoading(true);

      const response = await api.post(
        "/accounts/verify-email/",
        {
          email: email,
          otp: otp,
        }
      );

      console.log(
        "Email verification response:",
        response.data
      );

      setSuccess(
        response.data?.message ||
        "Email verified successfully."
      );

      sessionStorage.removeItem("verification_email");

      setTimeout(() => {
        navigate("/login");
      }, 1500);

    } catch (error) {
      console.error(
        "Email verification failed:",
        error
      );

      const data = error.response?.data;

      if (data?.message) {
        setError(data.message);
      } else if (data?.error) {
        setError(data.error);
      } else if (data?.detail) {
        setError(data.detail);
      } else {
        setError(
          "Unable to verify email. Please try again."
        );
      }

    } finally {
      setLoading(false);
    }
  };

  const handleBackToRegister = () => {
    sessionStorage.removeItem("verification_email");
    navigate("/register");
  };

  return (
    <div className="verify-email-page">

      <div className="verify-email-card">

        {/* ICON */}
        <div className="verify-email-logo">
          <MailCheck size={34} />
        </div>

        {/* TITLE */}
        <h1>Verify Your Email</h1>

        <p className="verify-email-subtitle">
          We have sent a 6-digit OTP to
        </p>

        <p className="verify-email-address">
          {email || "your email"}
        </p>

        {/* ERROR */}
        {error && (
          <div className="verify-email-error">
            {error}
          </div>
        )}

        {/* SUCCESS */}
        {success && (
          <div className="verify-email-success">
            {success}
          </div>
        )}

        {/* FORM */}
        <form onSubmit={handleSubmit}>

          <div className="verify-email-field">

            <label>
              Enter OTP
            </label>

            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="Enter 6-digit OTP"
              value={otp}
              onChange={handleOtpChange}
              disabled={loading}
              autoComplete="one-time-code"
            />

          </div>

          {/* VERIFY BUTTON */}
          <button
            type="submit"
            className="verify-email-button"
            disabled={loading}
          >
            {loading
              ? "Verifying..."
              : "Verify Email"}
          </button>

        </form>

        {/* BACK TO REGISTER */}
        <div className="verify-email-back">

          <button
            type="button"
            onClick={handleBackToRegister}
            disabled={loading}
          >
            <ArrowLeft size={16} />
            Back to Register
          </button>

        </div>

      </div>

    </div>
  );
}

export default VerifyEmail;