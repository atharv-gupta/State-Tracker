import "./globals.css";

export const metadata = {
  title: "State Activity Tracker",
  description: "What state governments are actually doing, in RAF's pillars",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
