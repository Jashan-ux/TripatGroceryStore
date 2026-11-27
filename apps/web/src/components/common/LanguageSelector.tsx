import { Select } from '@/components/ui/select';
import { getCurrentLanguage, setCurrentLanguage, t, type Language } from '@/i18n';

/** Compact language switch shared by the storefront and merchant console. */
export function LanguageSelector() {
  const language = getCurrentLanguage();

  return (
    <Select
      aria-label={t('common.language', language)}
      className="w-[86px] px-2 pr-7 text-xs"
      value={language}
      onChange={(event) => setCurrentLanguage(event.target.value as Language)}
    >
      <option value="en">EN</option>
      <option value="hi">हिंदी</option>
    </Select>
  );
}
