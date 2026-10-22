export interface ListOptions {
  /**
   * Only active rows — for pickers offering a new choice. Lookups that turn a
   * stored id into a name leave it unset, so an inactive row still resolves.
   */
  activeOnly?: boolean
}
