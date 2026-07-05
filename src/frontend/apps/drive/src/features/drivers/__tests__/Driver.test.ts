import { Driver } from "../Driver";

describe("Driver.createFileFromTemplate", () => {
  const buildDriver = () => {
    const createNewFile = jest.fn().mockResolvedValue({ id: "created-item" });
    const driver = Object.create(Driver.prototype) as Driver & {
      createNewFile: typeof createNewFile;
    };

    driver.createNewFile = createNewFile;

    return { driver, createNewFile };
  };

  it.each([
    {
      extension: ".ODT",
      title: " Report.odt ",
      expected: {
        filenameStem: "Report",
        extension: "odt",
        kind: "text",
      },
    },
    {
      extension: "ods",
      title: "Budget.ODS",
      expected: {
        filenameStem: "Budget",
        extension: "ods",
        kind: "sheet",
      },
    },
    {
      extension: ".odp",
      title: "Roadmap",
      expected: {
        filenameStem: "Roadmap",
        extension: "odp",
        kind: "slide",
      },
    },
  ])(
    "normalizes $extension, trims an existing suffix and maps the upstream kind",
    async ({ extension, title, expected }) => {
      const { driver, createNewFile } = buildDriver();

      const created = await driver.createFileFromTemplate({
        parentId: "parent-1",
        extension,
        title,
      });

      expect(createNewFile).toHaveBeenCalledWith({
        parentId: "parent-1",
        ...expected,
      });
      expect(created).toEqual({ id: "created-item" });
    },
  );

  it("keeps non-odf extensions unmapped while still delegating to createNewFile", async () => {
    const { driver, createNewFile } = buildDriver();

    await driver.createFileFromTemplate({
      extension: ".docx",
      title: "Quarterly report.docx.backup",
    });

    expect(createNewFile).toHaveBeenCalledWith({
      parentId: undefined,
      filenameStem: "Quarterly report.docx.backup",
      extension: "docx",
      kind: undefined,
    });
  });
});
