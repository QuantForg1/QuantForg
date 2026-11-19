import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LearnArticle } from "@/components/marketing/learn-article";
import { getLearnPage, LEARN_PAGES } from "@/lib/marketing/learn-catalog";

export function generateStaticParams() {
  return LEARN_PAGES.map((page) => ({ slug: page.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const page = getLearnPage(slug);
  if (!page) return { title: "Guide" };
  return {
    title: page.title,
    description: page.description,
    alternates: { canonical: `/learn/${page.slug}` },
    openGraph: {
      title: `${page.title} · QuantForg`,
      description: page.description,
      url: `/learn/${page.slug}`,
      images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg" }],
    },
  };
}

export default async function LearnSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const page = getLearnPage(slug);
  if (!page) notFound();
  return <LearnArticle page={page} />;
}
