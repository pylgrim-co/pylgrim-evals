export class DomainError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message);
    this.name = "DomainError";
  }
}

export class NotFoundError extends DomainError {
  constructor(what: string) {
    super(`${what} not found`, "not_found");
  }
}
