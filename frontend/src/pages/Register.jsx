import { useState } from "react";
import { Eye, EyeOff, UserPlus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";

function Register() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    password_confirm: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));

    setError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");

    const username = formData.username.trim();
    const email = formData.email.trim();

    if (!username) {
      setError("Username is required.");
      return;
    }

    if (!email) {
      setError("Email is required.");
      return;
    }

    if (!formData.password) {
      setError("Password is required.");
      return;
    }

    if (formData.password.length < 8) {
      setError(
        "Password must be at least 8 characters."
      );
      return;
    }

    if (!formData.password_confirm) {
      setError(
        "Please confirm your password."
      );
      return;
    }

    if (
      formData.password !==
      formData.password_confirm
    ) {
      setError(
        "Passwords do not match."
      );
      return;
    }

    try {
      setLoading(true);

      const response = await api.post(
        "/accounts/register/",
        {
          username,
          email,
          password: formData.password,
          password_confirm:
            formData.password_confirm,
        }
      );

      console.log(
        "Register response:",
        response.data
      );

      /*
       * Save email temporarily so OTP page
       * knows which email to verify.
       */
      sessionStorage.setItem(
        "verification_email",
        email
      );

      /*
       * Go to OTP verification page.
       */
      navigate("/verify-email");

    } catch (error) {
      console.error(
        "Registration failed:",
        error
      );

      console.error(
        "Response:",
        error.response?.data
      );

      const data =
        error.response?.data;

      if (data?.email) {
        setError(
          Array.isArray(data.email)
            ? data.email[0]
            : data.email
        );
      } else if (data?.username) {
        setError(
          Array.isArray(data.username)
            ? data.username[0]
            : data.username
        );
      } else if (data?.password) {
        setError(
          Array.isArray(data.password)
            ? data.password[0]
            : data.password
        );
      } else if (
        data?.password_confirm
      ) {
        setError(
          Array.isArray(
            data.password_confirm
          )
            ? data.password_confirm[0]
            : data.password_confirm
        );
      } else if (data?.detail) {
        setError(data.detail);
      } else if (data?.message) {
        setError(data.message);
      } else {
        setError(
          "Unable to create account."
        );
      }

    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-page">

      <div className="register-card">

        {/* LOGO */}

        <div className="register-logo">
          <UserPlus size={32} />
        </div>

        {/* TITLE */}

        <h1>
          Create Account
        </h1>

        <p className="register-subtitle">
          Create your account to start chatting
        </p>

        {/* ERROR */}

        {error && (
          <div className="register-error">
            {error}
          </div>
        )}

        {/* FORM */}

        <form onSubmit={handleSubmit}>

          {/* USERNAME */}

          <div className="register-field">

            <label>
              Username
            </label>

            <input
              type="text"
              name="username"
              placeholder="Enter username"
              value={formData.username}
              onChange={handleChange}
              disabled={loading}
              autoComplete="username"
            />

          </div>


          {/* EMAIL */}

          <div className="register-field">

            <label>
              Email
            </label>

            <input
              type="email"
              name="email"
              placeholder="Enter email"
              value={formData.email}
              onChange={handleChange}
              disabled={loading}
              autoComplete="email"
            />

          </div>


          {/* PASSWORD */}

          <div className="register-field">

            <label>
              Password
            </label>

            <div className="password-input-wrapper">

              <input
                type={
                  showPassword
                    ? "text"
                    : "password"
                }
                name="password"
                placeholder="Enter password"
                value={formData.password}
                onChange={handleChange}
                disabled={loading}
                autoComplete="new-password"
              />

              <button
                type="button"
                onClick={() =>
                  setShowPassword(
                    (previous) =>
                      !previous
                  )
                }
                disabled={loading}
                className="password-toggle"
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>

            </div>

          </div>


          {/* CONFIRM PASSWORD */}

          <div className="register-field">

            <label>
              Confirm Password
            </label>

            <div className="password-input-wrapper">

              <input
                type={
                  showConfirmPassword
                    ? "text"
                    : "password"
                }
                name="password_confirm"
                placeholder="Confirm password"
                value={
                  formData.password_confirm
                }
                onChange={handleChange}
                disabled={loading}
                autoComplete="new-password"
              />

              <button
                type="button"
                onClick={() =>
                  setShowConfirmPassword(
                    (previous) =>
                      !previous
                  )
                }
                disabled={loading}
                className="password-toggle"
              >
                {showConfirmPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>

            </div>

          </div>


          {/* REGISTER BUTTON */}

          <button
            type="submit"
            className="register-button"
            disabled={loading}
          >
            {loading
              ? "Creating account..."
              : "Create Account"}
          </button>

        </form>


        {/* LOGIN */}

        <div className="register-login">

          <span>
            Already have an account?
          </span>

          <button
            type="button"
            onClick={() =>
              navigate("/login")
            }
          >
            Login
          </button>

        </div>

      </div>

    </div>
  );
}

export default Register;