# Security Policy

SecureEye interacts directly with system authentication. It is designed with security in mind, but using facial 
recognition introduces inherent risks.

---

## Security Caveats

* Facial recognition is **not infallible** — false positives and false negatives may occur.
* Always use a **strong fallback authentication** (e.g., password).
* Physical access to the device can bypass protections (e.g., via photos or video spoofing).
* Environmental factors (lighting, camera quality) may impact reliability.
* PAM integration must be **tested carefully** before production deployment.
* SecureEye **does not replace full security audits**; follow system hardening best practices.

---

## Reporting Vulnerabilities

* Report security issues via **GitHub Issues** or direct email to the maintainer.
* Do **not disclose publicly** until a fix is available.
* Include reproduction steps, system details, and logs if safe to share.

---

## Secure Usage Recommendations

* Keep your system and Python dependencies **up to date**.
* Limit access to cameras and sensitive files.
* Run SecureEye in a **sandboxed or restricted environment** where possible.
* Regularly review authentication logs for anomalies.

---

## Disclaimer

SecureEye is provided **“as-is.”**  
The authors are **not liable** for misuse, misconfiguration, or bypasses.  
Users are responsible for **secure deployment and operational practices**.  