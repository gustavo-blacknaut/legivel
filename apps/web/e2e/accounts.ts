import accounts from "./accounts.json";

export type Account = { name: string; email: string; password: string; role: string };

export const ADMIN = accounts[0] as Account;
export const READER = accounts[1] as Account;
