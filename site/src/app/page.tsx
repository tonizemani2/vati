import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

export default function Home() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main" id="main">
        <RawSection name="hero" />
        <RawSection name="sampleqs" />
        <RawSection name="research" />
        <RawSection name="solutions" />
        <RawSection name="usecases" />
        <RawSection name="product" />
        <RawSection name="about" />
        <RawSection name="mission" />
        <RawSection name="footer" />
      </main>
      <RawSection name="contactModal" />
      <RawSection name="sampleqsModal" />
      <RawSection name="videoModal" />
      <SiteRuntime />
    </div>
  );
}
