import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ArenaOS from './ArenaOS.jsx';

/**
 * Behavioural checks for the prototype fixes in ArenaOS.jsx — the component is
 * really rendered in jsdom and assertions are made on what a user sees, the way
 * tests/test_teacher_portal_rbac.py checks the product.
 *
 * Two helpers keep the queries honest:
 *  - `deepest` drops ancestors, because every card wraps its children and an
 *    unscoped substring query matches the whole tree above it;
 *  - inputs are set with fireEvent.change, because user.type() into a
 *    type=number/date field is unreliable in jsdom (and it strips whitespace,
 *    which would hide the very bug fix 7 addresses).
 */

const today = () => new Date().toISOString().slice(0, 10);

// Scope every substring assertion to the element that actually renders it: the
// cards wrap their children, so a bare getByText('…') also matches every
// ancestor above the line we mean to assert on.
const inTag = (tag, text) => screen.getByText(text, undefined, { selector: tag });
const allInTag = (tag, text) => screen.getAllByText(text, undefined, { selector: tag });
// Cards are the only elements with a subject heading, but the manager board uses
// <h2> + .rounded-xl while the teacher portal uses <h3> + .rounded-2xl, so locate
// them by container and match on textContent rather than accessible name.
const card = (subject) => {
  const found = [...document.querySelectorAll('.rounded-xl, .rounded-2xl')].filter((el) => {
    const heading = el.querySelector('h2, h3');
    return heading && (heading.textContent || '').trim() === subject;
  });
  if (found.length !== 1) {
    throw new Error(
      `expected one card for "${subject}", found ${found.length} ` +
      `(${JSON.stringify([...document.querySelectorAll('h2, h3')].map((h) => h.textContent))})`
    );
  }
  return found[0];
};
const anyLine = (re) => [...document.querySelectorAll('p')].find((el) => re.test(el.textContent || ''));

const ID_LABEL = (content, node) =>
  node?.tagName === 'LABEL' && /Staff ID|Username/i.test(content);
const SECRET_LABEL = (content, node) =>
  node?.tagName === 'LABEL' && /PIN Code|Password/i.test(content);
const NAME_LABEL = (content, node) =>
  node?.tagName === 'LABEL' && content.trim() === 'Subject Name';

// The label and its control are siblings inside a wrapper div, so reach the
// control through the label's `for` id rather than by DOM order.
const labelInput = (text, { select = false } = {}) => {
  const label = screen.getByText(text);
  const el = document.getElementById(label.getAttribute('for'));
  if (!el) throw new Error(`label "${text}" has no associated control`);
  expect(el.tagName.toLowerCase()).toBe(select ? 'select' : 'input');
  return el;
};

const switchToManager = async (user) => {
  // The header chip "Logged in as: School Manager (Admin)" collides with the tab
  // once signed in, so the tab is always the first of the two matches.
  // The header chip "Logged in as: School Manager (Admin)" collides with the tab
  // once signed in, so the tab is always the first of the two matches.
  await user.click(screen.getAllByRole('button', { name: 'School Manager' })[0]);
  await waitFor(() =>
    expect(labelInput(SECRET_LABEL)).toHaveAttribute('placeholder', '••••••••')
  );
};

const submitLogin = async (user, { id, secret }) => {
  fireEvent.change(labelInput(ID_LABEL), { target: { value: id } });
  fireEvent.change(labelInput(SECRET_LABEL), { target: { value: secret } });
  await user.click(screen.getByRole('button', { name: /Authenticate & Access Dashboard/i }));
};

const loginAsManager = (user, { id = 'admin' } = {}) => submitLogin(user, { id, secret: 'admin123' });
const loginAsTeacher = (user) => submitLogin(user, { id: 'T-402', secret: '1234' });

const logout = async (user) => {
  await user.click(screen.getByRole('button', { name: 'Logout' }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'System Login' })).toBeInTheDocument());
};

const openAddSubjectForm = async (user) => {
  await user.click(screen.getByRole('button', { name: /Add Subject Syllabus/i }));
  await waitFor(() => expect(screen.getByText('Create New Subject Syllabus Entry')).toBeInTheDocument());
};

const createSubject = async (user, { subject, classGrade, target, deadline }) => {
  await openAddSubjectForm(user);
  fireEvent.change(labelInput(NAME_LABEL), { target: { value: subject } });
  if (classGrade) {
    await user.selectOptions(labelInput(/^Class Grade$/, { select: true }), classGrade);
  }
  if (target !== undefined) {
    fireEvent.change(labelInput(/^Target Benchmark %$/), { target: { value: String(target) } });
  }
  if (deadline !== undefined) {
    fireEvent.change(labelInput(/^Deadline$/), { target: { value: deadline } });
  }
  await user.click(screen.getByRole('button', { name: 'Save Subject Entry' }));
  await waitFor(() => expect(card(subject)).toBeTruthy(), { timeout: 1500 });
  return card(subject);
};

const openTopicsModal = async (user, cardHeading = 'Mathematics') => {
  const target = card(cardHeading);
  await user.click(within(target).getByRole('button', { name: /Log Topics/i }));
  await waitFor(() => expect(screen.getByText(/Curriculum Units$/)).toBeInTheDocument());
};

describe('Log Topics modal', () => {
  it('re-renders live unit state after each toggle (fix 1)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    await loginAsManager(user);
    await openTopicsModal(user);

    const progress = () => anyLine(/% covered · target 85%/);
    expect(progress()).toHaveTextContent('50% covered');
    const checkedCount = () => screen.getAllByRole('checkbox').filter((c) => c.checked).length;
    expect(checkedCount()).toBe(2);

    // Tick both remaining units from inside the modal.
    await user.click(screen.getAllByRole('checkbox').filter((c) => !c.checked)[0]);
    await waitFor(() => expect(checkedCount()).toBe(3));
    await user.click(screen.getAllByRole('checkbox').filter((c) => !c.checked)[0]);
    await waitFor(() => expect(checkedCount()).toBe(4));

    // The modal itself moved — previously it kept rendering the frozen snapshot
    // copied at open time and the boxes snapped straight back.
    expect(progress()).toHaveTextContent('100% covered');
    expect(card('Mathematics')).toHaveTextContent('Curriculum Progress: 100%');
  });

  it('can extend a plan with new units without closing (fix 8)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    await loginAsManager(user);
    await openTopicsModal(user);

    expect(anyLine(/50% covered · target 85% · 4 units/)).toBeTruthy();

    await user.click(screen.getByRole('button', { name: /Add Unit/i }));

    // A 5th unit lands uncovered, so the plan falls from 2/4 to 2/5.
    await waitFor(() => expect(anyLine(/40% covered · target 85% · 5 units/)).toBeTruthy());
    expect(screen.getByText(/^5 Units Configured$/)).toBeInTheDocument();
    expect(screen.getByText('Chapter 5: Untitled Unit')).toBeInTheDocument();

    // …and it is immediately tickable: 3/5 = 60%.
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes).toHaveLength(5);
    expect(boxes[4].checked).toBe(false);
    await user.click(boxes[4]);
    await waitFor(() => expect(anyLine(/60% covered · target 85% · 5 units/)).toBeTruthy());
  });
});

describe('Manager subject creation', () => {
  it('honours the target benchmark and keeps ids unique (fixes 4, 5)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    await loginAsManager(user);

    const chemistry = await createSubject(user, { subject: 'Chemistry', target: 95 });
    expect(chemistry).toHaveTextContent('Target Benchmark: 95%');
    expect(chemistry).toHaveTextContent('1 Units Configured');

    // A second row must not reuse the first row's generated id.
    await createSubject(user, { subject: 'Biology' });
    const biology = card('Biology');
    expect(biology).not.toBe(chemistry);
    expect(allInTag('h2', 'Chemistry')).toHaveLength(1);
    expect(allInTag('h2', 'Biology')).toHaveLength(1);
  });

  it('assigns the new subject to the teacher portal (fix 8)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    await loginAsManager(user);
    await createSubject(user, { subject: 'Chemistry' });
    await logout(user);

    // No tab switch needed: logout resets to the teacher tab (fix 10).
    await loginAsTeacher(user);
    expect(card('Chemistry')).toBeTruthy();
    expect(inTag('h2', /Your Active Subject Assignments \(3\)/)).toBeTruthy();
  });
});

describe('Attendance engine', () => {
  it('offers four statuses and keys the register to the live session date (fixes 4, 6)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await loginAsTeacher(user);

    for (const status of ['Present', 'Absent', 'Late', 'Excused']) {
      // 2 assigned subjects × 3 students in the mock roll
      expect(screen.getAllByRole('button', { name: status })).toHaveLength(6);
    }
    // The writer and the reader share SESSION_DATE, so the tally line is dated today.
    expect(allInTag('span', new RegExp(`0/3 on ${today()}`))).toHaveLength(2);
  });

  it('counts a roster and can mark it complete in one tap', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await loginAsTeacher(user);

    const tallies = () => [...document.querySelectorAll('span')].map((el) => el.textContent || '');
    await user.click(screen.getAllByRole('button', { name: 'Absent' })[0]);
    await waitFor(() => expect(tallies().some((t) => /^Absent: 1$/.test(t.trim()))).toBe(true), {
      timeout: 2000,
    });

    await user.click(screen.getAllByRole('button', { name: /Mark all present/i })[0]);
    await waitFor(() => expect(tallies().some((t) => /^Present: 3$/.test(t.trim()))).toBe(true), {
      timeout: 2000,
    });
    expect(tallies().some((t) => /^Absent: 0$/.test(t.trim()))).toBe(true);
    expect(allInTag('span', new RegExp(`3/3 on ${today()}`))).toHaveLength(1);
  });

  it('refuses to list another class roll on a subject (fix 6)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    await loginAsManager(user);
    await createSubject(user, { subject: 'Biology', classGrade: 'Class 8' });
    await logout(user);

    await loginAsTeacher(user);
    expect(card('Biology')).toBeTruthy();
    // T-402 now owns Biology/Class 8. The mock roll has no Class 8 students, so
    // that register stays empty instead of showing Form 3 names on a Class 8 card.
    expect(anyLine(/No enrolled students match Class 8/)).toBeTruthy();
    expect(screen.getAllByText('Ahmed Mohamed Farah', { exact: true })).toHaveLength(2);
  });

  it('keeps the restricted portal to the signed-in teacher', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await loginAsTeacher(user);
    expect(screen.getByRole('heading', { name: 'Teacher Subject Portal' })).toBeInTheDocument();
    // Both Class 11 periods of T-402 carry the same three-name mock roll...
    expect(screen.getAllByText('Ahmed Mohamed Farah', { exact: true })).toHaveLength(2);
    // ...and Mr. Jama Farah's Humanities assignment never surfaces here.
    expect(screen.queryByRole('heading', { name: 'Somali Literature' })).not.toBeInTheDocument();
  });
});

describe('Login', () => {
  it('normalises manager usernames (fix 7)', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await switchToManager(user);
    // Pasted straight in: trailing space and wrong case must still authenticate.
    await loginAsManager(user, { id: 'Admin ' });
    expect(
      await screen.findByRole('heading', { name: 'Syllabus & Curriculum Administration' })
    ).toBeInTheDocument();
  });

  it('rejects a bad PIN', async () => {
    const user = userEvent.setup();
    render(<ArenaOS />);
    await submitLogin(user, { id: 'T-402', secret: '0000' });
    expect(screen.getByText(/Invalid Staff ID or PIN/)).toBeInTheDocument();
  });
});
