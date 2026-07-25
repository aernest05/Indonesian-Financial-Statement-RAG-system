-- FinSage Supabase schema
-- Run this once in the Supabase SQL editor for project fagjsrbdaslepmuvyplt
-- (Dashboard -> SQL Editor -> New query -> paste -> Run)

-- ── Chat history (accessed directly by the frontend with the user's JWT) ──

create table if not exists public.chat_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New conversation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists chat_conversations_user_id_idx on public.chat_conversations(user_id);

alter table public.chat_conversations enable row level security;

create policy "Users can view own conversations"
  on public.chat_conversations for select
  using (auth.uid() = user_id);

create policy "Users can insert own conversations"
  on public.chat_conversations for insert
  with check (auth.uid() = user_id);

create policy "Users can update own conversations"
  on public.chat_conversations for update
  using (auth.uid() = user_id);

create policy "Users can delete own conversations"
  on public.chat_conversations for delete
  using (auth.uid() = user_id);


create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.chat_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  context_docs jsonb,
  extracted_years jsonb,
  created_at timestamptz not null default now()
);

create index if not exists chat_messages_conversation_id_idx on public.chat_messages(conversation_id);

alter table public.chat_messages enable row level security;

create policy "Users can view messages in own conversations"
  on public.chat_messages for select
  using (
    exists (
      select 1 from public.chat_conversations c
      where c.id = chat_messages.conversation_id and c.user_id = auth.uid()
    )
  );

create policy "Users can insert messages in own conversations"
  on public.chat_messages for insert
  with check (
    exists (
      select 1 from public.chat_conversations c
      where c.id = chat_messages.conversation_id and c.user_id = auth.uid()
    )
  );


-- ── Billing / quota (backend only, via SUPABASE_SERVICE_KEY — RLS blocks everyone else) ──

create table if not exists public.subscriptions (
  user_id uuid primary key references auth.users(id) on delete cascade,
  status text not null default 'free',
  expires_at timestamptz,
  midtrans_order_id text,
  midtrans_transaction_id text,
  updated_at timestamptz not null default now()
);

alter table public.subscriptions enable row level security;
-- No policies defined on purpose: only the service_role key (used by the FastAPI
-- backend) can read/write this table; anon/authenticated clients are denied by default.

create table if not exists public.query_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  date date not null,
  count int not null default 0,
  unique (user_id, date)
);

alter table public.query_usage enable row level security;
-- Same as above: service_role only.
