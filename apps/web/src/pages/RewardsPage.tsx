import type { ScratchCardOut } from '@tripat/api-client';
import {
  BadgeCheck,
  Copy,
  Check,
  Gift,
  Sparkles,
  Ticket,
  Trophy,
  Wallet as WalletIcon,
} from 'lucide-react';
import { useState } from 'react';

import { EmptyState } from '@/components/common/EmptyState';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useJoinReferral,
  useRevealCard,
  useRewards,
  useScratchCards,
} from '@/features/rewards/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { formatDateOnly, formatIst, formatPaise } from '@/lib/utils';
import { cn } from '@/lib/utils';

const REASON_COPY: Record<string, string> = {
  referral_bonus: 'Referral reward',
  scratch_card: 'Scratch card',
  return_refund: 'Return refund',
  order_payment: 'Paid on an order',
  adjustment: 'Adjustment',
};

const TIER_COPY: Record<string, string> = {
  none: 'Member',
  gold: 'Gold member',
  platinum: 'Platinum member',
  diamond: 'Diamond member',
};

/**
 * Rewards.
 *
 * Four things in one place because they are the same question to a customer —
 * "what have I got?" — but they answer differently: the wallet is money, the card
 * is a surprise, the code is for sending to a friend, and the badge is progress.
 */
export default function RewardsPage() {
  usePageTitle(undefined, 'Rewards');
  const rewards = useRewards();

  if (rewards.isPending) {
    return (
      <div className="container max-w-2xl space-y-3 py-6">
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (rewards.isError || !rewards.data) {
    return (
      <div className="container max-w-2xl py-8">
        <EmptyState
          icon={Trophy}
          title="We could not load your rewards"
          body="Check your connection and try again."
          action={
            <Button className="mt-2" onClick={() => void rewards.refetch()}>
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  const { wallet, referrals, tier } = rewards.data;

  return (
    <div className="container max-w-2xl space-y-4 py-6 pb-nav-safe md:pb-8">
      <h1 className="text-xl font-extrabold tracking-tight">Rewards</h1>

      {/* Wallet */}
      <section
        aria-labelledby="wallet-heading"
        className="rounded-xl border border-border bg-card p-4"
      >
        <div className="flex items-center gap-2">
          <WalletIcon className="size-4 text-primary" aria-hidden="true" />
          <h2 id="wallet-heading" className="text-sm font-bold">
            Wallet
          </h2>
        </div>
        <p className="mt-1 text-3xl font-extrabold tabular-nums">
          {formatPaise(wallet.balance_paise)}
        </p>
        <p className="text-xs text-muted-foreground">
          Spendable on any order — choose it at checkout.
        </p>
        {wallet.entries.length > 0 ? (
          <ul className="mt-3 divide-y divide-border text-sm">
            {wallet.entries.slice(0, 6).map((entry) => (
              <li key={entry.id} className="flex items-start justify-between gap-3 py-2">
                <span className="min-w-0">
                  <span className="block font-medium">
                    {REASON_COPY[entry.reason] ?? entry.reason}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {formatIst(entry.created_at, {
                      day: 'numeric',
                      month: 'short',
                      hour: 'numeric',
                      minute: '2-digit',
                    })}
                    {entry.note ? ` · ${entry.note}` : ''}
                  </span>
                </span>
                <span
                  className={cn(
                    'shrink-0 font-bold tabular-nums',
                    entry.delta_paise > 0 ? 'text-primary' : 'text-muted-foreground',
                  )}
                >
                  {entry.delta_paise > 0 ? '+' : '−'}
                  {formatPaise(Math.abs(entry.delta_paise))}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            Nothing in it yet. Refer a friend, or rub off a card from a big order.
          </p>
        )}
      </section>

      {/* Scratch cards */}
      <ScratchSection />

      {/* Referral */}
      <section
        aria-labelledby="referral-heading"
        className="rounded-xl border border-border bg-card p-4"
      >
        <div className="flex items-center gap-2">
          <Gift className="size-4 text-primary" aria-hidden="true" />
          <h2 id="referral-heading" className="text-sm font-bold">
            Invite a friend
          </h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          They get {referrals.friend_discount_pct}% off their first order. You get{' '}
          {formatPaise(referrals.referrer_reward_paise)} in your wallet once that order is
          delivered.
        </p>
        <CodeRow code={referrals.code} shareUrl={referrals.share_url} />
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="text-muted-foreground">Friends</dt>
            <dd className="text-base font-bold tabular-nums">{referrals.joined}</dd>
          </div>
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="text-muted-foreground">Paid out</dt>
            <dd className="text-base font-bold tabular-nums">{referrals.credited}</dd>
          </div>
          <div className="rounded-lg bg-muted/60 p-2">
            <dt className="text-muted-foreground">Earned</dt>
            <dd className="text-base font-bold tabular-nums">
              {formatPaise(referrals.earned_paise)}
            </dd>
          </div>
        </dl>
        {referrals.friends.length > 0 && (
          <ul className="mt-3 space-y-1 text-sm">
            {referrals.friends.map((friend, index) => (
              <li key={`${friend.name}-${index}`} className="flex justify-between gap-2">
                <span>
                  {friend.name}
                  <span className="text-xs text-muted-foreground"> · {friend.status}</span>
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {formatPaise(friend.reward_paise)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {referrals.my_referral ? (
          <p className="mt-3 rounded-lg bg-muted/60 p-2 text-xs">
            You joined with <span className="font-semibold">{referrals.my_referral.code}</span>
            {referrals.my_referral.referrer_name
              ? ` (${referrals.my_referral.referrer_name})`
              : ''}{' '}
            · {referrals.my_referral.status}
          </p>
        ) : (
          <JoinCode />
        )}
      </section>

      {/* Badge */}
      <section
        aria-labelledby="tier-heading"
        className="rounded-xl border border-border bg-card p-4"
      >
        <div className="flex items-center gap-2">
          <Trophy className="size-4 text-primary" aria-hidden="true" />
          <h2 id="tier-heading" className="text-sm font-bold">
            {TIER_COPY[tier.tier] ?? 'Member'}
          </h2>
          {tier.tier !== 'none' && (
            <BadgeCheck className="size-4 text-primary" aria-hidden="true" />
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {formatPaise(tier.spend_paise)} of delivered orders (returns not counted).
        </p>
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={tier.progress_pct}
          aria-label="Progress to the next badge"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${tier.progress_pct}%` }}
          />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {tier.next_tier_at_paise === null
            ? 'Top badge — thank you.'
            : `${formatPaise(tier.remaining_paise)} more for ${TIER_COPY[tier.next_tier ?? ''] ?? 'the next badge'}.`}
        </p>
      </section>
    </div>
  );
}

/** The code, with a copy button that says it worked. */
function CodeRow({ code, shareUrl }: { code: string; shareUrl: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    const link = `${window.location.origin}${shareUrl}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="mt-2 flex items-center gap-2">
      <code className="flex-1 rounded-lg border border-dashed border-border px-3 py-2 text-base font-extrabold tracking-[0.2em]">
        {code}
      </code>
      <Button variant="outline" size="sm" onClick={() => void copy()}>
        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
        {copied ? 'Copied' : 'Copy link'}
      </Button>
    </div>
  );
}

/** "Have a friend's code?" — refused by the API if it is too late or not theirs. */
function JoinCode() {
  const join = useJoinReferral();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  return (
    <form
      className="mt-3 flex items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        setError(null);
        join.mutate(code.trim().toUpperCase(), {
          onSuccess: () => setCode(''),
          onError: (err) => setError(err.message),
        });
      }}
    >
      <div className="flex-1">
        <label htmlFor="referral-code" className="mb-1 block text-xs font-semibold">
          Got a friend&apos;s code?
        </label>
        <Input
          id="referral-code"
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase())}
          maxLength={12}
          placeholder="ABCDEF"
          autoComplete="off"
        />
      </div>
      <Button
        type="submit"
        size="sm"
        variant="outline"
        disabled={code.trim().length < 4 || join.isPending}
      >
        {join.isPending ? 'Saving…' : 'Use code'}
      </Button>
      {error && (
        <p role="alert" className="w-full text-xs font-medium text-primary-700">
          {error}
        </p>
      )}
    </form>
  );
}

/** Cards: locked (order not delivered), ready (rub it off), revealed (what you won). */
function ScratchSection() {
  const cards = useScratchCards();
  const reveal = useRevealCard();
  const [error, setError] = useState<string | null>(null);

  if (cards.isPending) return <Skeleton className="h-36 w-full rounded-xl" />;
  const list = cards.data?.cards ?? [];

  return (
    <section
      aria-labelledby="cards-heading"
      className="rounded-xl border border-border bg-card p-4"
    >
      <div className="flex items-center gap-2">
        <Ticket className="size-4 text-primary" aria-hidden="true" />
        <h2 id="cards-heading" className="text-sm font-bold">
          Scratch cards
        </h2>
      </div>
      {list.length === 0 ? (
        <p className="mt-1 text-sm text-muted-foreground">
          Orders of {formatPaise(200000)} or more earn a card, unlocked when they arrive.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {list.map((card) => (
            <ScratchCardRow
              key={card.id}
              card={card}
              pending={reveal.isPending && reveal.variables === card.id}
              onReveal={() => {
                setError(null);
                reveal.mutate(card.id, { onError: (err) => setError(err.message) });
              }}
            />
          ))}
        </ul>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs font-medium text-primary-700">
          {error}
        </p>
      )}
    </section>
  );
}

function ScratchCardRow({
  card,
  pending,
  onReveal,
}: {
  card: ScratchCardOut;
  pending: boolean;
  onReveal: () => void;
}) {
  const locked = card.status === 'locked';
  const ready = card.status === 'ready';
  const revealed = card.status === 'revealed' || card.status === 'used';

  return (
    <li
      className={cn(
        'rounded-lg border p-3',
        ready ? 'border-primary-200 bg-primary-50/60' : 'border-border bg-background',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-bold">
            {revealed && card.amount_paise != null
              ? `You won ${formatPaise(card.amount_paise)}`
              : locked
                ? 'Locked until delivery'
                : card.status === 'void'
                  ? 'This card is no longer valid'
                  : 'Ready to scratch'}
          </p>
          <p className="text-xs text-muted-foreground">
            {card.order_number ? `${card.order_number} · ` : ''}
            {locked
              ? 'It unlocks the moment the order is delivered.'
              : revealed && card.revealed_at
                ? `Revealed ${formatIst(card.revealed_at, { day: 'numeric', month: 'short' })} · the money is in your wallet`
                : card.expires_at
                  ? `Use it by ${formatDateOnly(card.expires_at, { day: 'numeric', month: 'short', year: 'numeric' })}`
                  : ''}
          </p>
        </div>
        {ready ? (
          <Button size="sm" onClick={onReveal} disabled={pending}>
            <Sparkles aria-hidden="true" />
            {pending ? 'Scratching…' : 'Scratch'}
          </Button>
        ) : (
          <span className="shrink-0 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {card.status}
          </span>
        )}
      </div>
    </li>
  );
}
