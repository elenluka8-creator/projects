import { getTranslations } from "next-intl/server";
import { AppShell } from "@/components/AppShell";

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "legal" });
  return { title: `${t("privacyTitle")} — Unfolda` };
}

const sectionStyle = {
  marginBottom: "2rem",
};

const h2Style = {
  fontSize: "1.125rem",
  fontWeight: 600,
  marginBottom: "0.75rem",
  color: "var(--color-navy)",
};

const pStyle = {
  fontSize: "0.9375rem",
  lineHeight: "1.75",
  color: "var(--color-navy)",
  opacity: 0.8,
  marginBottom: "0.75rem",
};

const liStyle = {
  fontSize: "0.9375rem",
  lineHeight: "1.75",
  color: "var(--color-navy)",
  opacity: 0.8,
  marginBottom: "0.375rem",
};

export default async function PrivacyPage({ params }: Props) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "legal" });

  return (
    <AppShell>
      <article
        className="mx-auto max-w-2xl py-12"
        style={{ color: "var(--color-navy)" }}
      >
        <header style={{ marginBottom: "2.5rem" }}>
          <h1
            className="font-heading text-3xl"
            style={{ marginBottom: "0.5rem", color: "var(--color-navy)" }}
          >
            {t("privacyTitle")}
          </h1>
          <p style={{ fontSize: "0.875rem", opacity: 0.5, marginBottom: "0.25rem" }}>
            {t("lastUpdated")}
          </p>
          <p style={{ fontSize: "0.875rem", opacity: 0.5 }}>{t("bindingNote")}</p>
        </header>

        <section style={sectionStyle}>
          <h2 style={h2Style}>1. Introduction</h2>
          <p style={pStyle}>
            Unfolda (&ldquo;we&rdquo;, &ldquo;us&rdquo;, &ldquo;our&rdquo;) is committed to protecting
            your privacy. This Privacy Policy explains what information we collect, how we use it, and
            your rights regarding your personal data when you use the Unfolda translation service.
          </p>
          <p style={pStyle}>
            By using the Service you agree to the collection and use of information as described in this
            Policy. If you do not agree, please do not use the Service.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>2. Information We Collect</h2>
          <p style={pStyle}>We collect the following categories of information:</p>
          <ul style={{ paddingLeft: "1.25rem", marginBottom: "0.75rem", listStyleType: "disc" }}>
            <li style={liStyle}>
              <strong>Account information:</strong> Your Google account email address and display name,
              obtained via Google OAuth when you sign in.
            </li>
            <li style={liStyle}>
              <strong>Uploaded content:</strong> EPUB files you upload for translation. These are stored
              temporarily for processing and delivery.
            </li>
            <li style={liStyle}>
              <strong>Job metadata:</strong> Configuration choices you make (target language, translation mode,
              quality tier), word counts, submission timestamps, and job status.
            </li>
            <li style={liStyle}>
              <strong>Usage data:</strong> Server-side logs including request timestamps, IP addresses,
              and error events, retained for operational security purposes.
            </li>
          </ul>
          <p style={pStyle}>
            We do not collect payment card information directly. We do not use advertising SDKs,
            behavioural tracking pixels, or third-party analytics services.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>3. How We Use Your Information</h2>
          <p style={pStyle}>We use the information we collect to:</p>
          <ul style={{ paddingLeft: "1.25rem", marginBottom: "0.75rem", listStyleType: "disc" }}>
            <li style={liStyle}>Authenticate you and manage your account.</li>
            <li style={liStyle}>Process your translation requests using AI language models.</li>
            <li style={liStyle}>Deliver translated output files to you.</li>
            <li style={liStyle}>Calculate and deduct credits for completed jobs.</li>
            <li style={liStyle}>Monitor service health, investigate errors, and prevent abuse.</li>
            <li style={liStyle}>Communicate with you about your account or the Service when necessary.</li>
          </ul>
          <p style={pStyle}>
            We do not use your content to train AI models. Your uploaded files are used solely for the
            translation job you submit.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>4. Data Retention</h2>
          <p style={pStyle}>
            <strong>Uploaded and translated files</strong> are automatically deleted 30 days after
            submission. This window is defined by the <code>RETENTION_WINDOW_DAYS</code> configuration
            parameter. Files cannot be recovered after deletion.
          </p>
          <p style={pStyle}>
            <strong>Account data</strong> (email, credit balance, job history metadata) is retained for
            as long as your account is active. You may request deletion of your account and all associated
            data at any time by contacting us.
          </p>
          <p style={pStyle}>
            <strong>Server logs</strong> are retained for up to 90 days for security and operational purposes.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>5. Third-Party Services</h2>
          <p style={pStyle}>
            To provide the Service we share data with the following third-party processors:
          </p>
          <ul style={{ paddingLeft: "1.25rem", marginBottom: "0.75rem", listStyleType: "disc" }}>
            <li style={liStyle}>
              <strong>Google LLC (Google OAuth):</strong> Used for authentication. Google processes your
              account information in accordance with{" "}
              <a
                href="https://policies.google.com/privacy"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--color-navy)", textDecoration: "underline" }}
              >
                Google&rsquo;s Privacy Policy
              </a>.
            </li>
            <li style={liStyle}>
              <strong>Anthropic PBC (Claude API):</strong> The text content of your uploaded EPUB is sent
              to Anthropic&rsquo;s API for translation processing. Anthropic processes this data as a
              sub-processor under their API terms. We do not share your personal account information
              with Anthropic.
            </li>
          </ul>
          <p style={pStyle}>
            We do not share your data with any other third parties, advertisers, or data brokers.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>6. Data Security</h2>
          <p style={pStyle}>
            We implement industry-standard security measures to protect your data, including encrypted
            connections (TLS), access controls, and secure storage. However, no method of internet
            transmission or electronic storage is 100% secure. We cannot guarantee absolute security.
          </p>
          <p style={pStyle}>
            In the event of a data breach that affects your rights and freedoms, we will notify you as
            required by applicable law.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>7. Your Rights</h2>
          <p style={pStyle}>
            Depending on your location, you may have the following rights regarding your personal data:
          </p>
          <ul style={{ paddingLeft: "1.25rem", marginBottom: "0.75rem", listStyleType: "disc" }}>
            <li style={liStyle}><strong>Access:</strong> Request a copy of the personal data we hold about you.</li>
            <li style={liStyle}><strong>Correction:</strong> Request correction of inaccurate personal data.</li>
            <li style={liStyle}><strong>Deletion:</strong> Request deletion of your account and all associated personal data.</li>
            <li style={liStyle}><strong>Portability:</strong> Request your data in a portable format.</li>
            <li style={liStyle}><strong>Objection:</strong> Object to certain types of processing.</li>
          </ul>
          <p style={pStyle}>
            To exercise any of these rights, please contact us through the support channel in your
            account settings. We will respond within 30 days.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>8. No Selling of User Data</h2>
          <p style={pStyle}>
            <strong>We do not sell, rent, or otherwise transfer your personal data to third parties for
            commercial or marketing purposes.</strong> Your data is used exclusively to provide the
            translation service you requested.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>9. Cookies and Local Storage</h2>
          <p style={pStyle}>
            The Service uses a <strong>strictly necessary session cookie</strong> to maintain your
            authenticated session after you sign in via Google OAuth. This cookie is essential for the
            Service to function and does not require consent under ePrivacy rules for strictly necessary
            cookies.
          </p>
          <p style={pStyle}>
            We also use <strong>browser localStorage</strong> to store your UI preferences (such as
            cookie consent acknowledgement). No personal data is stored in localStorage.
          </p>
          <p style={pStyle}>
            We do not use tracking cookies, advertising cookies, or any third-party cookie scripts.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>10. Changes to This Policy</h2>
          <p style={pStyle}>
            We may update this Privacy Policy from time to time. We will notify users of material changes
            by updating the &ldquo;Last updated&rdquo; date at the top of this page. Your continued use
            of the Service after changes are posted constitutes acceptance of the revised Policy.
          </p>
        </section>

        <section style={sectionStyle}>
          <h2 style={h2Style}>11. Contact</h2>
          <p style={pStyle}>
            If you have questions about this Privacy Policy or wish to exercise your data rights, please
            contact us through the support channel listed in your account settings.
          </p>
        </section>
      </article>
    </AppShell>
  );
}
