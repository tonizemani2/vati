// Live test of the credits/quota SQL against Neon. Cleans up after itself.
import { getAccount, consume, addCredits } from "../src/lib/credits";
import { db } from "../src/lib/db";

const U = "test-user-" + "qa-credits";

function show(label: string, x: unknown) {
  console.log(label.padEnd(28), JSON.stringify(x));
}

async function main() {
  const sql = db();
  // clean slate
  await sql`delete from credit_ledger where user_id = ${U}`;
  await sql`delete from user_credits where user_id = ${U}`;

  show("fresh account", await getAccount(U));
  show("consume quick (free)", await consume(U, "quick"));
  show("council #1", (await consume(U, "council")).valueOf());
  show("council #2", await consume(U, "council"));
  show("council #3", await consume(U, "council"));
  show("council #4 (should fail)", await consume(U, "council"));
  show("deep w/o credits (fail)", await consume(U, "deep"));

  show("addCredits 25 (sess A)", await addCredits(U, 25, "sess_A"));
  show("addCredits 25 dup (sess A)", await addCredits(U, 25, "sess_A")); // idempotent -> false
  show("account after topup", await getAccount(U));

  show("council on credits", await consume(U, "council")); // mode credit, 24 left
  show("deep on credits (-4)", await consume(U, "deep")); // 20 left
  show("final account", await getAccount(U));

  // cleanup
  await sql`delete from credit_ledger where user_id = ${U}`;
  await sql`delete from user_credits where user_id = ${U}`;
  console.log("\ncleaned up.");
}
main().catch((e) => {
  console.error(e);
  process.exit(1);
});
