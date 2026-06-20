import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

export default function Home() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main" id="main">
        <RawSection name="hero" />
        {/* One claim, then the proof. The calls are the product; everything below is the receipt. */}
        <RawSection name="forecasts" />
        {/* Early reads already moving our way on live price anchors (was record + the duplicate "track" section, now just one). */}
        <RawSection name="record" />
        {/* The method + the leak-free ForecastBench benchmark. */}
        <RawSection name="research" />
        {/* Who we are: a small, self-taught lab. Keeps a human face instead of an anonymous oracle. */}
        <RawSection name="about" />
        {/* The quiet door: point the engine at a client mandate (institutional finance). */}
        <RawSection name="engage" />
        <RawSection name="footer" />
      </main>
      <RawSection name="contactModal" />
      <RawSection name="videoModal" />
      <SiteRuntime />
    </div>
  );
}
